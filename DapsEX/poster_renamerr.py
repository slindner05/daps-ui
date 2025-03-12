import json
import logging
import re
import shutil
import datetime
import os
from collections.abc import Callable
from pathlib import Path
from pprint import pformat

from pathvalidate import sanitize_filename
from tqdm import tqdm

from DapsEX import utils
from DapsEX.border_replacerr import BorderReplacerr
from DapsEX.database_cache import Database
from DapsEX.logger import init_logger
from DapsEX.media import Radarr, Server, Sonarr
from DapsEX.settings import Settings
from progress import ProgressState


class PosterRenamerr:
    def __init__(self, payload):
        self.logger = logging.getLogger("PosterRenamerr")
        try:
            log_dir = Path(Settings.LOG_DIR.value) / Settings.POSTER_RENAMERR.value
            init_logger(
                self.logger,
                log_dir,
                "poster_renamerr",
                log_level=payload.log_level if payload.log_level else logging.INFO,
            )
            supported_options = ["black", "remove", "custom"]
            self.db = Database(self.logger)
            self.target_path = Path(payload.target_path)
            self.backup_dir = Path(Settings.ORIGINAL_POSTERS.value)
            if not self.backup_dir.exists():
                self.backup_dir.mkdir()
            self.source_directories = payload.source_dirs
            self.asset_folders = payload.asset_folders
            self.clean_assets = payload.clean_assets
            self.upload_to_plex = payload.upload_to_plex
            self.match_alt = payload.match_alt
            self.only_unmatched = payload.only_unmatched
            self.replace_border = payload.replace_border

            if payload.border_setting in supported_options:
                self.border_setting = payload.border_setting
            else:
                self.logger.warning(
                    f"Invalid border color setting: {payload.border_setting}. Border replacerr will not run."
                )
                self.border_setting = None
                self.replace_border = False
            if self.border_setting == "custom" or self.border_setting == "black":
                if payload.custom_color and utils.is_valid_hex_color(
                    payload.custom_color
                ):
                    self.custom_color = payload.custom_color
                else:
                    self.logger.warning(
                        f"Invalid hex color code: {payload.custom_color}. Border replacerr will not run."
                    )
                    self.custom_color = None
                    self.replace_border = False
            else:
                self.custom_color = ""
                self.replace_border = payload.replace_border

            self.border_replacerr = BorderReplacerr(custom_color=self.custom_color)
            self.plex_instances = utils.create_plex_instances(
                payload, Server, self.logger
            )
            self.radarr_instances, self.sonarr_instances = utils.create_arr_instances(
                payload, Radarr, Sonarr, self.logger
            )

        except Exception as e:
            self.logger.exception("Failed to initialize PosterRenamerr")
            raise e

    image_exts = {".png", ".jpg", ".jpeg"}

    # only need to compile this once
    poster_id_pattern = re.compile(r"\{(imdb|tmdb|tvdb)-([a-zA-Z0-9]+)\}")
    year_pattern = re.compile(r"\b(19|20)\d{2}\b")

    # length to use as a prefix.  anything shorter than this will be used as-is
    prefix_length = 3

    asset_list_file = "asset_list.json"

    def preprocess_name(self, name: str) -> str:
        """
        Preprocess a name for consistent matching:
        - Convert to lowercase
        - Remove special characters
        - Remove common words
        """
        # Convert to lowercase and remove special characters
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        # Remove extra whitespace
        name = ' '.join(name.split())

        # Optionally remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to'}
        # maybe for collections we need to _not_ do this? i.e. 'FX.jpg vs. FX Collection' - only an issue when a collection name is 1 or 2 chars...
        return ''.join(word for word in name.split() if word not in common_words)

    def save_cached_structs_to_disk(self, assets_list, path, logger):
        """
        Persist asset list to disk to avoid future runs having to re-process all of the posters
        """
        asset_list_path = os.path.join(path, self.asset_list_file)
        with open(asset_list_path, 'w') as file:
            json.dump(assets_list, file)


    def load_cached_structs(self, path, refresh_after_n_hours, logger):
        """
        load the asset list from disk
        """

        assets_list = None
        asset_list_path = os.path.join(path, self.asset_list_file)
        if os.path.isfile(asset_list_path):
            created_time_epoch = os.path.getctime(asset_list_path)
            created_datetime = datetime.datetime.fromtimestamp(created_time_epoch)
            if refresh_after_n_hours > 0:
                    if (datetime.datetime.now() - created_datetime) >= datetime.timedelta(hours=refresh_after_n_hours):
                        logger.info(f"existing file was created more than {refresh_after_n_hours} ago, forcing a refresh")
                        return None
            try:
                with open(asset_list_path, 'r') as file:
                    assets_list = json.load(file)
            except Exception as e:
                logger.info(f"Failure to load asset file from disk: {e}")
        return assets_list

    def build_search_index(self, prefix_index, title, asset, asset_type, logger, debug_items=None):
        """
        Build an index of preprocessed movie names for efficient lookup
        Returns both the index and preprocessed forms
        """
        asset_type_processed_forms = prefix_index[asset_type]
        processed = self.preprocess_name(title)
        debug_build_index = debug_items and len(debug_items) > 0 and processed in debug_items

        if debug_build_index:
            logger.info('debug_build_search_index')
            logger.info(processed)
            logger.info(asset_type)
            logger.info(asset)

        # Store word-level index for partial matches
        words = processed.split()
        if debug_build_index:
            logger.info(words)

        # only need to do the first word here
        # also - store add to a prefix to expand possible matches
        for word in words:
        # if len(word) > 2 or len(words)==1:  # Only index words longer than 2 chars unless it's the only word
            if word not in asset_type_processed_forms:
                asset_type_processed_forms[word] = list() #maybe consider moving to dequeue?
            asset_type_processed_forms[word].append(asset)

            # also add the prefix.  if shorter than prefix_length then it was already added above.
            if len(word) > self.prefix_length:
                prefix = word[0:self.prefix_length]
                if debug_build_index:
                    logger.info(prefix)
                if prefix not in asset_type_processed_forms:
                    asset_type_processed_forms[prefix] = list()
                asset_type_processed_forms[prefix].append(asset)
            break

        return

    def search_matches(self, prefix_index, movie_title, asset_type, logger, debug_search=False):
        """ search for matches in the index """
        matches = list()
        
        processed_filename = self.preprocess_name(movie_title)
        asset_type_processed_forms = prefix_index[asset_type]

        if (debug_search):
            logger.info('debug_search_matches')
            logger.info(processed_filename)

        words = processed_filename.split()
        if (debug_search):
            logger.info(words)
        # Try word-level matches
        for word in words:
            # first add any prefix matches to the beginning of the list.
            if len(word) > self.prefix_length:
                prefix = word[0:self.prefix_length]
                if (debug_search):
                    logger.info(prefix)
                    logger.info(prefix in asset_type_processed_forms)

                if prefix in asset_type_processed_forms:
                    matches.extend(asset_type_processed_forms[prefix])

            # then add the full word matches as items.
            # TODO: is this even needed any more given everything would grab the prefix
            #       or maybe this is an else to the above?
            if word in asset_type_processed_forms:
                matches.extend(asset_type_processed_forms[word])
            if (debug_search):
                logger.info(matches)
            break

        return matches

    def _log_banner(self):
        self.logger.info("\n" + "#" * 80)
        self.logger.info("### New PosterRenamerr Run")
        self.logger.info("\n" + "#" * 80)

    def clean_cache(self) -> None:
        try:
            asset_files = [str(item) for item in Path(self.target_path).rglob("*")]
            cached_file_data = self.db.return_all_files()
            cached_file_paths = list(cached_file_data.keys())

            for item in cached_file_paths:
                if item not in asset_files:
                    self.db.delete_cached_file(item)
                    self.logger.debug(f"Cleaned {item} from database")
        except Exception as e:
            self.logger.error(f"Error cleaning cache: {e}")

    def clean_asset_dir(self, media_dict, collections_dict) -> None:
        try:
            directories_to_clean = [self.target_path, self.backup_dir]
            asset_files = (
                item
                for dir_path in directories_to_clean
                for item in dir_path.rglob("*")
                if item.is_file()
            )
            titles = (
                set(
                    utils.remove_chars(movie["title"])
                    for movie in media_dict.get("movies", [])
                )
                .union(
                    set(
                        utils.remove_chars(show["title"])
                        for show in media_dict.get("shows", [])
                    )
                )
                .union(
                    set(
                        utils.remove_chars(collection.replace("/", ""))
                        for collection in collections_dict.get("movies", [])
                    )
                )
                .union(
                    set(
                        utils.remove_chars(collection.replace("/", ""))
                        for collection in collections_dict.get("shows", [])
                    )
                )
            )
            removed_asset_count = 0
            directories_to_remove = []

            if self.asset_folders:
                self.logger.info(
                    "Detected asset folder configuration. Attempting to remove invalid assets."
                )
            else:
                self.logger.info(
                    "Detected flat asset configuration. Attempting to remove invalid assets."
                )
            for item in asset_files:
                parent_dir = item.parent
                if self.asset_folders:
                    if parent_dir == self.target_path or parent_dir == self.backup_dir:
                        self.logger.info(f"Removing orphaned asset file --> {item}")
                        item.unlink()
                        removed_asset_count += 1
                    else:
                        asset_title = utils.remove_chars(parent_dir.name)
                        if asset_title not in titles:
                            directories_to_remove.append(parent_dir)
                            removed_asset_count += 1
                else:
                    asset_pattern = re.search(r"^(.*?)(?:_.*)?$", item.stem)
                    if asset_pattern:
                        asset_title = utils.remove_chars(asset_pattern.group(1))
                        if asset_title not in titles:
                            self.logger.info(f"Removing orphaned asset file --> {item}")
                            item.unlink()
                            removed_asset_count += 1

            for directory in directories_to_remove:
                self._remove_directory(directory)

            for dir_path in directories_to_clean:
                for sub_dir in dir_path.rglob("*"):
                    if sub_dir.is_dir() and not any(sub_dir.iterdir()):
                        sub_dir.rmdir()

            self.logger.info(
                f"Removed {removed_asset_count} items from asset directories."
            )

        except Exception as e:
            self.logger.error(f"Error cleaning assets: {e}")

    def _remove_directory(self, directory: Path):
        if directory.exists() and directory.is_dir():
            self.logger.info(f"Removing orphaned asset directory: {directory}")
            for sub_item in list(directory.iterdir()):
                if sub_item.is_file():
                    sub_item.unlink()
            if directory.exists():
                directory.rmdir()

    def get_source_files(self) -> dict[str, list[Path]]:
        source_directories = [Path(item) for item in self.source_directories]
        source_files = {}
        unique_files = set()

        with tqdm(
            total=len(source_directories), desc="Processing directories"
        ) as dir_progress:
            for source_dir in source_directories:
                if not source_dir.is_dir():
                    self.logger.warning(f"{source_dir} is not a valid directory.")
                    dir_progress.update(1)
                    continue
                for poster in source_dir.rglob("*"):
                    if not poster.is_file():
                        self.logger.error(f"{poster} is not a file")
                        continue
                    if poster.suffix.lower() not in self.image_exts:
                        self.logger.debug(f"⏩ Skipping non-image file: {poster}")
                        continue
                    if poster.name in unique_files:
                        # self.logger.debug(f"⏩ Skipping duplicate file: {poster}")
                        continue
                    unique_files.add(poster.name)
                    source_files.setdefault(source_dir, []).append(poster)

                if (source_dir in source_files):
                    # Sort files alphabetically to make processing and matching more consistent
                    source_files[source_dir] = sorted(source_files[source_dir], key=lambda x: x.as_posix().lower())
                dir_progress.update(1)

        return source_files

    def handle_movie_match(self, matched_movies, file, movie_data, movie_has_file, movie_status, webhook_run, sanitized_name_without_extension, sanitized_movie_title, unique_items):
        matched_movies[file] = {
            "has_file": movie_has_file,
            "status": movie_status,
            "match": movie_data
        }
        if webhook_run:
            matched_movies[file]["webhook_run"] = (
                webhook_run
            )
        unique_items.add(sanitized_name_without_extension)
        unique_items.add(sanitized_movie_title)

    def is_season_complete(self, show_seasons, show_data):
        return not show_seasons and "series_poster_matched" in show_data and show_data["series_poster_matched"]

    def handle_show_season_match(self, season, matched_shows, file, show_data, webhook_run, unique_items, main_match, sanitized_name_without_extension, alt_matches, show_seasons):
        season_has_episodes = season.get(
            "has_episodes", None
        )
        matched_shows[file] = {
            "has_episodes": season_has_episodes,
            "match": show_data,
        }
        if webhook_run:
            matched_shows[file][
                "webhook_run"
            ] = webhook_run
        unique_items.add(main_match)
        unique_items.add(
            sanitized_name_without_extension
        )
        if alt_matches:
            unique_items.update(alt_matches)
        # remove to determine later if we have all of the seasons
        show_seasons.remove(season)
        

    def handle_show_series_match(self, matched_shows, file, show_status, show_has_episodes, webhook_run, unique_items, sanitized_name_without_extension, sanitized_show_name, alt_titles_clean, show_seasons, show_data):
        show_name = show_data.get("title", "")
        matched_shows[file] = {
            "status": show_status,
            "has_episodes": show_has_episodes,
            "match": show_data,
        }
        if webhook_run:
            matched_shows[file]["webhook_run"] = (
                webhook_run
            )
        unique_items.add(sanitized_name_without_extension)
        unique_items.add(sanitized_show_name)
        if alt_titles_clean:
            unique_items.update(alt_titles_clean)
        show_data["series_poster_matched"] = True
        self.logger.debug(
            f"Show seasons: {show_seasons}"
        )


    def compute_asset_values_for_match(self, search_match) -> None:
        file = search_match['file'] # given a search match we can pre-compute (& store) values
        # this will compute values if they don't already exist and put them back onto the search match.
        if not 'computed_attributes' in search_match:
            search_match['computed_attributes'] = True
            search_match['name_without_extension'] = file.stem
            search_match['sanitized_name_without_extension'] = utils.remove_chars(search_match['name_without_extension'])
            search_match['sanitized_file_name_without_collection'] = search_match['sanitized_name_without_extension'].removesuffix(" collection")
            year_match = re.search(r"\((\d{4})\)", search_match['name_without_extension']) # should we improve this ?
            search_match['has_season_info'] = bool(re.search(r" - (season|specials)", search_match['name_without_extension'], re.IGNORECASE))
            search_match['poster_file_year'] = year_match.group(1) if year_match else None
            poster_id = self.poster_id_pattern.search(search_match['name_without_extension'])
            search_match['poster_id'] = poster_id.group(0) if poster_id else None
            season_num_match = re.search(r"- Season (\d+)", search_match['name_without_extension'], re.IGNORECASE)
            search_match['season_num'] = int(season_num_match.group(1)) if season_num_match else None


    def match_files_with_media(
        self,
        source_files: dict[str, list[Path]],
        media_dict: dict[str, list],
        collections_dict: dict[str, list[str]],
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
    ) -> dict[str, dict[Path, str | bool]]:
        matched_files = {
            "collections": [],
            "movies": {},
            "shows": {},
        }
        unique_items = set()

        flattened_col_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        movies_list_copy = media_dict.get("movies", [])[:]
        shows_list_copy = media_dict.get("shows", [])[:]

        # total_files = sum(len(files) for files in source_files.values())
        total_directories = len(source_files)
        processed_files = 0
        items_indexed = 0
        total_media_files = len(movies_list_copy) + len(flattened_col_list) + len(shows_list_copy)
        total_files = total_media_files
        # dict per asset type to map asset prefixes to the assets, themselves.
        prefix_index = {
            'movies': {},
            'shows': {},
            'collections': {},
            'all': {} # for now using this as "catch all"
        }

        with tqdm(
            total=total_directories, desc="Processing directories"
        ) as progress_bar:
            for directory, files in source_files.items():
                self.logger.info(f"Processing directory: {directory}")
                for file in files:
                    name_without_extension = file.stem
                    # could add an id --> file lookup here :-) 
                    # not building an asset type index here yet since we process assets on-the-fly
                    # everything will be placed into the 'all' asset type for now
                    file_ref = {'file': file}
                    self.build_search_index(prefix_index, name_without_extension, file_ref, "all", self.logger, debug_items=None)
                    items_indexed += 1
                progress_bar.update(1)
            self.logger.info(f"all directories processed and index is built. Found {items_indexed} posters")
        with tqdm(
            total=total_media_files, desc="Processing media files for matches"
        ) as progress_bar:
            # now the index is built... let's use it instead of looping over the dirs.
            # now to loop over media...
            # need to loop over copy here...
            matched_collections = 0
            unmatched_collections = 0
            for collection_name in flattened_col_list[:]:
                matched_collection_files = self.find_collection_matches(prefix_index, collection_name, unique_items)
                num_matches = len(matched_collection_files["collections"])
                if (num_matches > 0):
                    matched_collections += 1
                    matched_files["collections"].extend(matched_collection_files["collections"])
                else: 
                    unmatched_collections += 1
                    self.logger.info(f"No match found for collection {collection_name}")

                progress_bar.update(1)
                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)
            
            # looping over a copy, but guessing we don't need to 
            # and I can delete the remove line maybe?
            matched_movies = 0
            unmatched_movies = 0
            for movie_data in movies_list_copy[:]:
                # neat idea _maybe_? why not just do all the alt matches lookups here? it would still scan them in priority order... so it comes down to the cost of the lookups
                # or better need to extract all of this into a function so we can 1) all for main movie, check result, and if not matched then 2) loop and call for alt titles
                matched_movie_files = self.find_movie_matches(prefix_index, movie_data.get("title", ""), unique_items, movie_data)
                num_matches = len(matched_movie_files["movies"])
                if (num_matches > 0):
                    matched_movies += 1
                    # merge the new match with existing matches
                    matched_files["movies"] = matched_files["movies"] | matched_movie_files["movies"]
                else: 
                    unmatched_movies += 1
                    self.logger.info(f"No match found for movie {movie_data.get('title', '')}")
                
                progress_bar.update(1)
                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)

            fully_matched_shows = 0
            unmatched_shows = 0
            partial_matched_shows = 0
            partial_matched_missing_seasons = 0
            partial_matched_missing_poster = 0
            partial_matched_only_missing_specials = 0
            matches_found_with_alt_title_searches = 0
            alt_title_searches_performed = 0
            for show_data in shows_list_copy[:]:
                if self.match_alt or show_data.get("webhook_run", None):
                    alt_titles_clean = [utils.remove_chars(alt) for alt in show_data.get("alternate_titles", [])]
                    show_year = re.search(r"\((\d{4})\)", show_data.get("title", ""))
                    if show_year:
                        alt_titles_clean = [alt if self.year_pattern.search(alt) else f"{alt} {show_year.group(1)}" for alt in alt_titles_clean]
                else:
                    alt_titles_clean = []

                titles_to_search = [show_data.get("title", "")]
                # append alt titles to the end.  Will only be used if the main title search isn't found
                titles_to_search.extend(alt_titles_clean)
                main_title_search = True
                self.logger.debug(f"titles_to_search: {titles_to_search}")
                found_a_match = False
                for title in titles_to_search:
                    if main_title_search:
                        self.logger.debug(f"doing main title search for {show_data.get('title', '')} of: {title}")
                    else:
                        alt_title_searches_performed += 1
                        self.logger.debug(f"doing alt title search for {show_data.get('title', '')} of: {title}")
                    matched_show_files = self.find_series_matches(prefix_index, title, unique_items, show_data)
                    num_matches= len(matched_show_files["shows"])
                    matched_entire_show = matched_show_files["matched_entire_show"]
                    # this will have been updated from within the lookup function.
                    if (num_matches > 0):
                        if not main_title_search:
                            matches_found_with_alt_title_searches += 1
                        found_a_match = True
                        matched_files["shows"] = matched_files["shows"] | matched_show_files["shows"]

                        # if we found a match, but it wasn't the entire show, let's get some stats
                        if not matched_entire_show:
                            self.logger.debug(f"partial_match encountered {show_data}")
                            partial_matched_shows += 1
                            show_seasons = show_data.get("seasons", [])
                            for season in show_seasons:
                                if "season00" in season.get("season", "") and len(show_seasons) == 1:
                                    partial_matched_only_missing_specials += 1
                                if (season['has_episodes']):
                                    partial_matched_missing_seasons += 1
                                    break
                            if not "series_poster_matched" in show_data or ("series_poster_matched" in show_data and not show_data["series_poster_matched"]):
                                partial_matched_missing_poster += 1
                        else:
                            fully_matched_shows += 1
                        break # if we found any match then we stop here vs. searching for alt titles
                    main_title_search = False

                if not found_a_match:
                    unmatched_shows += 1
                    self.logger.info(f"No match found for show {show_data.get('title', '')}")

                progress_bar.update(1)
                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)
        
        self.logger.info(f"matched_collections: {matched_collections}") # should be accurate
        self.logger.info(f"unmatched_collections: {unmatched_collections}") # should be accurate
        self.logger.info(f"matched_movies: {matched_movies}") # can be higher than expected due to items in radarr but not w/ files
        self.logger.info(f"unmatched_movies: {unmatched_movies}") # can be higher than expected due to items in radarr but not w/ files / not released 
        self.logger.info(f"fully_matched_shows: {fully_matched_shows}") # this means poster + all seasons
        self.logger.info(f"partial_matched_shows: {partial_matched_shows}") # this means something was missing - a season or poster, etc.
        self.logger.info(f"partial_matched_shows_missing_seasons: {partial_matched_missing_seasons}") # this means a season had espisodes and wasn't found
        self.logger.info(f"partial_matched_shows_missing_poster: {partial_matched_missing_poster}") # this means a poster was missing
        self.logger.info(f"partial_matched_shows_missing_only_specials: {partial_matched_only_missing_specials}") # this means only the specials season was missing
        self.logger.info(f"matches_found_with_alt_title_searches: {matches_found_with_alt_title_searches}")
        self.logger.info(f"alt_title_searches_performed: {alt_title_searches_performed}")
        self.logger.debug("Matched files summary:")
        self.logger.debug(pformat(matched_files))
        return matched_files

    def find_series_matches(self, prefix_index, search_title, unique_items, show_data):
        matched_files = {"shows": {},
                         "matched_entire_show" : False}
        search_matches = self.search_matches(prefix_index, search_title, "all", self.logger, debug_search=False)
        self.logger.debug(f"SEARCH (shows): matched assets for {show_data.get('title', '')}")
        self.logger.debug(search_matches)
                
        # really inefficient for now but I have to ensure we loop over _ever single match since seasons are calculated on the fly based on the files
        # this is expensive - especially since we don't remove items from the match list (though we could....)
        # the better solution is not to remove things but instead to pre-calculate seasons based on the asset files and then when you match you get everything in one shot
        # prob want to do an entire pass with main matches... then secondary pass with alt titles here... can't do it from within
        # ORRR use the alt titles here as well, but then also would need to do searches after?
        matched_entire_show = False
        for search_match in search_matches:
            self.compute_asset_values_for_match(search_match)
            file = search_match['file']
            name_without_extension = search_match['name_without_extension']
            sanitized_name_without_extension = search_match['sanitized_name_without_extension']
            sanitized_file_name_without_collection = search_match['sanitized_file_name_without_collection']
            poster_file_year = search_match['poster_file_year']
            poster_id = search_match['poster_id']
            has_id = bool(search_match['poster_id'])
            has_season_info = search_match['has_season_info']
            season_num = search_match['season_num']

            if (sanitized_name_without_extension in unique_items or sanitized_file_name_without_collection in unique_items):
                self.logger.debug(f"Skipping already matched file '{file}'")
                continue

            if not poster_file_year:
                self.logger.debug(f"Skipping collection file: '{file}'")
                continue # it's a collection, skip it.

            show_name = show_data.get("title", "")
            show_year = re.search(r"\((\d{4})\)", show_name)
            show_status = show_data.get("status", "")
            show_seasons = show_data.get("seasons", [])
            show_has_episodes = show_data.get("has_episodes", None)
            webhook_run = show_data.get("webhook_run", None)
            sanitized_show_name = utils.remove_chars(utils.strip_id(show_name))

            # need to do something here around alt titles
            # TODO: need to find matches based on the alt and loop through those *IFFF* the main one doesn't find a match.
            if self.match_alt or webhook_run:
                alt_titles_clean = [utils.remove_chars(alt) for alt in show_data.get("alternate_titles", [])]
                if show_year:
                    year_pattern = re.compile(r"\b(19|20)\d{2}\b")
                    alt_titles_clean = [alt if year_pattern.search(alt) else f"{alt} {show_year.group(1)}" for alt in alt_titles_clean]
            else:
                alt_titles_clean = []

            matched_season = False
            series_poster_matched = show_data.get("series_poster_matched", False)

            if season_num:
                self.logger.debug(f"found a season num ({season_num}) for file {file}, trying to match_show_season")
                result = self._match_show_season(name_without_extension, show_name, alt_titles_clean, self.poster_id_pattern, check_id=has_id)
                self.logger.debug(f"results: {result}")
                if isinstance(result, tuple):
                    main_match, alt_matches = result
                    for season in show_seasons[:]:
                        season_str = season.get("season", "")
                        season_str_match = re.match(r"season(\d+)", season_str)
                        if season_str_match:
                            media_season_num = int(season_str_match.group(1))
                            if season_num == media_season_num:
                                self.logger.debug(f"Matched season {season_num} for show: {show_name} with {file}")
                                self.handle_show_season_match(season, matched_files["shows"], file, show_data, webhook_run, unique_items, main_match, sanitized_name_without_extension, alt_matches, show_seasons)                                        
                                matched_season = True
                                break # this break is fine
                    if matched_season:
                        if (self.is_season_complete(show_seasons, show_data)):
                            # self.logger.debug(f"show seasons: {show_seasons}")
                            # self.logger.debug(f"show_data: {show_data}")
                            self.logger.debug(f"All seasons and series poster matched for {show_name}")
                            matched_entire_show = True
                            break # can stop looping if we have everything
                        continue # otherwise keep looping

            if not matched_season:
                self.logger.debug(f"no match yet for file {file}, trying to match_show_special")
                result = self._match_show_special(name_without_extension, show_name, alt_titles_clean, self.poster_id_pattern, check_id=has_id,)
                self.logger.debug(f"results: {result}")
                if isinstance(result, tuple):
                    main_match, alt_matches = result
                    for season in show_seasons[:]:
                        if "season00" in season.get("season", ""):
                            self.logger.debug(f"Matched special season for show: {show_name}")
                            self.handle_show_season_match(season, matched_files["shows"], file, show_data, webhook_run, unique_items, main_match, sanitized_name_without_extension, alt_matches, show_seasons)
                            matched_season = True
                            break # don't need to process more seasons
                if matched_season:
                    if (self.is_season_complete(show_seasons, show_data)):
                        self.logger.debug(f"All seasons and series poster matched for {show_name}")
                        matched_entire_show = True
                        break # can stop looping if we have everything
                    continue # otherwise keep looping

            if not matched_season:
                # why is id match so far down? that should take precedence, no?
                self.logger.debug(f"no match yet for file {file}, trying to match_id")
                id_match = False
                if has_id:
                    show_id_match = self.poster_id_pattern.search(show_name)
                    id_match = bool(poster_id and (poster_id == show_id_match.group(0) if show_id_match else None))
                    # only need to check the id match if the match has an id
                    if id_match:
                        self.logger.debug(f"Matched series poster for show (by ID): {show_name} with {file}")
                        self.handle_show_series_match(matched_files["shows"], file, show_status, show_has_episodes, webhook_run, unique_items, sanitized_name_without_extension, 
                                                      sanitized_show_name, alt_titles_clean, show_seasons,show_data)
                        if (self.is_season_complete(show_seasons, show_data)):
                            self.logger.debug(f"All seasons and series poster matched for {show_name}")
                            matched_entire_show = True
                            break # can stop looping if we have everything
                        continue # otherwise keep looping
                self.logger.debug(f"no id match yet for file {file}, trying to sanitized names")

                if (sanitized_name_without_extension == sanitized_show_name):
                    self.logger.debug(f"Matched series poster for show: {show_name} with {file}")
                    self.handle_show_series_match(matched_files["shows"], file, show_status, show_has_episodes, webhook_run, unique_items, sanitized_name_without_extension, "", 
                                                  alt_titles_clean, show_seasons, show_data)
                    if (self.is_season_complete(show_seasons, show_data)):
                        self.logger.debug(f"All seasons and series poster matched for {show_name}")
                        matched_entire_show = True
                        break # can stop looping if we have everything
                    continue # otherwise keep looping
                # TODO: this is where I need to deal with alt titles... search for matches and re-loop _everything_
                self.logger.debug(f"no match yet for file {file}, trying to match alt titles")

                if alt_titles_clean:
                    # this is saying for the orig matches do any alt matches match.... but separately we need to do lookups based on alt matches most likely
                    for alt_title in alt_titles_clean:
                        if (sanitized_name_without_extension == alt_title):
                            self.logger.debug(f"Matched series poster for show: {show_name} with {file}")
                            # change this to likely take a list of things to add to unique items vs. 2 with an empty string
                            self.handle_show_series_match(matched_files["shows"], file, show_status, show_has_episodes, webhook_run, unique_items, sanitized_show_name, "",
                                                          alt_titles_clean, show_seasons,show_data)
                            if (self.is_season_complete(show_seasons, show_data)):
                                self.logger.debug(f"All seasons and series poster matched for {show_name}")
                                matched_entire_show = True
                                break # can stop looping if we have everything
                            continue # otherwise keep looping
                # perhaps here we now look at alt titles and re-do logic above?
        matched_files["matched_entire_show"] = matched_entire_show
        return matched_files

    def find_movie_matches(self, prefix_index, search_title, unique_items, movie_data):
        matched_files = {"movies": {}}
        search_matches = self.search_matches(prefix_index, search_title, "all", self.logger, debug_search=False)
        self.logger.debug(f"SEARCH (movies): matched assets for {movie_data.get('title', '')}")
        self.logger.debug(search_matches)
        for search_match in search_matches:
            self.compute_asset_values_for_match(search_match)
            file = search_match['file']
            name_without_extension = search_match['name_without_extension']
            sanitized_name_without_extension = search_match['sanitized_name_without_extension']
            sanitized_file_name_without_collection = search_match['sanitized_file_name_without_collection']
            poster_file_year = search_match['poster_file_year']
            poster_id = search_match['poster_id']
            has_id = bool(search_match['poster_id'])
            has_season_info = search_match['has_season_info']

            if (sanitized_name_without_extension in unique_items or sanitized_file_name_without_collection in unique_items):
                self.logger.debug(f"Skipping already matched file '{file}'")
                continue

            if poster_file_year and not has_season_info:
                movie_title = movie_data.get("title", "")
                movie_years = movie_data.get("years", [])
                movie_status = movie_data.get("status", "")
                movie_has_file = movie_data.get("has_file", None)
                webhook_run = movie_data.get("webhook_run", None)
                sanitized_movie_title = utils.remove_chars(utils.strip_id(movie_title))
                sanitized_movie_title_without_year = utils.remove_chars(utils.strip_year(utils.strip_id(movie_title)))

                if has_id:
                    # we really only need to get the movie title here since we pre-compute the poster id string above..
                    movie_id_match = self.poster_id_pattern.search(movie_title)
                    id_match = bool(poster_id and (poster_id == movie_id_match.group(0) if movie_id_match else None))

                    if id_match:
                        self.logger.debug(f"Found exact match for movie (by ID): {movie_title} with {file}")
                        self.handle_movie_match(matched_files["movies"], file, movie_data, movie_has_file, movie_status, webhook_run, sanitized_name_without_extension, sanitized_movie_title, unique_items)
                        break # found a match break the search match loop

                if (sanitized_name_without_extension == sanitized_movie_title):
                    self.logger.debug(f"Found exact match for movie: {movie_title} with {file}")
                    self.handle_movie_match(matched_files["movies"], file, movie_data, movie_has_file, movie_status, webhook_run, sanitized_name_without_extension, utils.remove_chars(movie_title), unique_items)
                    break # found a match break the search match loop

                elif movie_years:
                    for year in movie_years:
                        sanitized_movie_title_alternate_year = (f"{sanitized_movie_title_without_year} {year}")
                        if (sanitized_name_without_extension == sanitized_movie_title_alternate_year):
                            self.logger.debug(f"Found year based match for movie: {movie_title} with {file}")
                            self.handle_movie_match(matched_files["movies"], file, movie_data, movie_has_file, movie_status, webhook_run, sanitized_name_without_extension, "", unique_items)
                            break # found a match break the search match loop
        return matched_files             

    # need to return some data here... prob just a boolean for "did we find a match"
    def find_collection_matches(self, prefix_index, collection_name, unique_items):
        matched_files = {"collections": []}
        search_matches = self.search_matches(prefix_index, collection_name, "all", self.logger, debug_search=False)
        self.logger.debug(f"SEARCH (collections): matched assets for {collection_name}")
        self.logger.debug(search_matches)
        for search_match in search_matches:
            self.compute_asset_values_for_match(search_match)
            file = search_match['file']
            name_without_extension = search_match['name_without_extension']
            sanitized_name_without_extension = search_match['sanitized_name_without_extension']
            sanitized_file_name_without_collection = search_match['sanitized_file_name_without_collection']
            poster_file_year = search_match['poster_file_year']
            poster_id = search_match['poster_id']
            has_id = bool(search_match['poster_id'])
            has_season_info = search_match['has_season_info']

            if (sanitized_name_without_extension in unique_items or sanitized_file_name_without_collection in unique_items):
                self.logger.debug(f"Skipping already matched file '{file}'")
                continue

            if not poster_file_year and not has_season_info:
                # already know we're in collections... but the above check could still be true 
                # since we're looping over matches across all asset types...
                sanitized_collection_name = utils.remove_chars(collection_name).removesuffix(" collection")
                if (sanitized_file_name_without_collection == sanitized_collection_name):
                    # instead of appending just the file... append the entire match to avoid re-finding again in copy/rename
                    collection_object = {'file': file}
                    collection_object['match'] = collection_name
                    matched_files["collections"].append(collection_object)
                    unique_items.add(sanitized_file_name_without_collection)
                    self.logger.debug(f"Matched collection poster for {collection_name} with {file}")
                    break
        return matched_files 

    def _match_id(self, file_name: str, media_name: str, poster_id_pattern: re.Pattern):
        poster_id_match = poster_id_pattern.search(file_name)
        media_id_match = poster_id_pattern.search(media_name)

        if poster_id_match and media_id_match:
            return poster_id_match.group(0) == media_id_match.group(0)

        return False

    def _match_show_season(
        self,
        file_name: str,
        show_name: str,
        alternate_titles: list,
        poster_id_pattern: re.Pattern,
        check_id: bool = False,
    ) -> bool | tuple[str, set[str]]:
        if check_id and not self._match_id(file_name, show_name, poster_id_pattern):
            return False

        sanitized_show_name_with_id = utils.remove_chars(show_name)
        sanitized_show_name = utils.remove_chars(utils.strip_id(show_name))
        sanitized_file_name = utils.remove_chars(utils.strip_id(file_name))
        alt_titles = set()
        season_pattern = re.compile(
            rf"{re.escape(sanitized_show_name)} season (\d+)", re.IGNORECASE
        )
        main_match = season_pattern.match(sanitized_file_name)

        if main_match:
            season_num = main_match.group(1)
            main_title = f"{sanitized_show_name} season {season_num}"
            id_title = f"{sanitized_show_name_with_id} season {season_num}"
            alt_titles.add(id_title)
            for alt_title in alternate_titles:
                alt_titles.add(f"{alt_title} season {season_num}")
            return main_title, alt_titles
        else:
            for alt_title in alternate_titles:
                season_pattern_alt = re.compile(
                    rf"{re.escape(alt_title)} season (\d+)",
                    re.IGNORECASE,
                )
                alt_match = season_pattern_alt.match(sanitized_file_name)
                if alt_match:
                    season_num = alt_match.group(1)
                    main_title = f"{sanitized_show_name} season {season_num}"
                    for alt_title in alternate_titles:
                        alt_titles.add(f"{alt_title} season {season_num}")
                    return main_title, alt_titles
        return False

    def _match_show_special(
        self,
        file_name: str,
        show_name: str,
        alternate_titles: list,
        poster_id_pattern: re.Pattern,
        check_id: bool = False,
    ) -> bool | tuple[str, set[str]]:
        if check_id and not self._match_id(file_name, show_name, poster_id_pattern):
            return False

        sanitized_show_name_with_id = utils.remove_chars(show_name)
        sanitized_show_name = utils.remove_chars(utils.strip_id(show_name))
        sanitized_file_name = utils.remove_chars(utils.strip_id(file_name))
        alt_titles = set()
        specials_pattern = re.compile(
            rf"{re.escape(sanitized_show_name)} specials", re.IGNORECASE
        )
        main_match = specials_pattern.match(sanitized_file_name)
        if main_match:
            main_title = f"{sanitized_show_name} specials"
            id_title = f"{sanitized_show_name_with_id} specials"
            alt_titles.add(id_title)
            for alt_title in alternate_titles:
                alt_titles.add(f"{alt_title} specials")
            return main_title, alt_titles

        else:
            for alt_title in alternate_titles:
                specials_pattern_alt = re.compile(
                    rf"{re.escape(alt_title)} specials",
                    re.IGNORECASE,
                )
                alt_match = specials_pattern_alt.match(sanitized_file_name)
                if alt_match:
                    main_title = f"{sanitized_show_name} specials"
                    for alt_title in alternate_titles:
                        alt_titles.add(f"{alt_title} specials")
                    return main_title, alt_titles
        return False

    def get_unmatched_media_dict(self) -> dict[str, list]:
        media_dict = {"movies": [], "shows": []}
        unmatched_show_arr_ids = self.db.get_unmatched_arr_ids("unmatched_shows")
        unmatched_movie_arr_ids = self.db.get_unmatched_arr_ids("unmatched_movies")

        for arr_id, instance_name in unmatched_movie_arr_ids:
            instance = self.radarr_instances.get(instance_name)
            if instance:
                try:
                    media_dict["movies"].extend(instance.get_movie(arr_id))
                except Exception as e:
                    self.logger.error(
                        f"Failed to fetch movie with ID {arr_id} from instance '{instance_name}': {e}"
                    )
            else:
                self.logger.error(f"No Radarr instance found for '{instance_name}'")

        for arr_id, instance_name in unmatched_show_arr_ids:
            instance = self.sonarr_instances.get(instance_name)
            if instance:
                try:
                    media_dict["shows"].extend(instance.get_show(arr_id))
                except Exception as e:
                    self.logger.error(
                        f"Failed to fetch show with ID {arr_id} from instance '{instance_name}': {e}"
                    )
            else:
                self.logger.error(f"No Sonarr instance found for '{instance_name}'")

        return media_dict

    def get_unmatched_collections_dict(self):
        collections_dict = {"all_collections": []}
        unmatched_collections = self.db.get_unmatched_assets("unmatched_collections")
        for collection in unmatched_collections:
            if "title" in collection:
                collections_dict["all_collections"].append(collection["title"])
        return collections_dict

    def log_matched_file(
        self, type: str, name: str, file_name: str, season_special_name: str = ""
    ) -> None:
        """Log a matched file with a structured format."""
        if type.lower() in {"season", "special"}:
            self.logger.debug(
                f"""
            -------------------------------------------------------
            Matched {type.capitalize()}:
                - Show name: {name}
                - {type.capitalize()}: {season_special_name}
                - File: {file_name}
            -------------------------------------------------------
            """
            )
        else:
            self.logger.debug(
                f"""
            -------------------------------------------------------
            Matched {type.capitalize()}:
                - {type.capitalize()}: {name}
                - File: {file_name}
            -------------------------------------------------------
            """
            )

    def _copy_file(
        self,
        file_path: Path,
        media_type: str,
        target_dir: Path,
        backup_dir: Path | None,
        new_file_name: str,
        replace_border: bool = False,
        status: str | None = None,
        has_episodes: bool | None = None,
        has_file: bool | None = None,
        webhook_run: bool | None = None,
    ) -> None:
        temp_path = None
        target_path = target_dir / new_file_name
        if backup_dir:
            backup_path = backup_dir / new_file_name
        else:
            backup_path = self.backup_dir / new_file_name
        file_name_without_extension = target_path.stem
        original_file_hash = utils.hash_file(file_path, self.logger)
        cached_file = self.db.get_cached_file(str(target_path))
        current_source = str(file_path)

        if target_path.exists() and cached_file:
            cached_hash = cached_file["file_hash"]
            cached_original_hash = cached_file["original_file_hash"]
            cached_source = cached_file["source_path"]
            cached_border_state = cached_file.get("border_replaced", 0)
            cached_border_setting = cached_file.get("border_setting", None)
            cached_custom_color = cached_file.get("custom_color", None)
            cached_has_episodes = cached_file.get("has_episodes", None)
            cached_has_file = cached_file.get("has_file", None)
            cached_status = cached_file.get("status", None)

            # Debugging: Log the current and cached values for comparison
            self.logger.debug(f"Checking skip conditions for file: {file_path}")
            self.logger.debug(f"File name: {file_name_without_extension}")
            self.logger.debug(f"Original file hash: {original_file_hash}")
            self.logger.debug(f"Cached hash: {cached_hash}")
            self.logger.debug(f"Cached original hash: {cached_original_hash}")
            self.logger.debug(f"Current source: {current_source}")
            self.logger.debug(f"Cached source: {cached_source}")
            self.logger.debug(f"Replace border (current): {replace_border}")
            self.logger.debug(f"Cached border replaced: {cached_border_state}")
            self.logger.debug(f"Cached border color: {cached_border_setting}")
            self.logger.debug(f"Current border color: {self.border_setting}")
            self.logger.debug(f"Cached custom color: {cached_custom_color}")
            self.logger.debug(f"Current custom color: {self.custom_color}")
            self.logger.debug(f"Cached status: {cached_status}")
            self.logger.debug(f"Current status: {status}")
            self.logger.debug(f"Cached has_episodes: {cached_has_episodes}")
            self.logger.debug(f"Current has_episodes: {has_episodes}")
            self.logger.debug(f"Cached has_file: {cached_has_file}")
            self.logger.debug(f"Current has_file: {has_file}")

            if cached_has_episodes is None or cached_has_episodes != has_episodes:
                if has_episodes is not None:
                    self.logger.debug(
                        f"Updating 'has_episodes' for {target_path}: {cached_has_episodes} -> {has_episodes}"
                    )
                    self.db.update_has_episodes(str(target_path), has_episodes)

            if cached_has_file is None or cached_has_file != has_file:
                if has_file is not None:
                    self.logger.debug(
                        f"Updating 'has_file' for {target_path}: {cached_has_file} -> {has_file}"
                    )
                    self.db.update_has_file(str(target_path), has_file)

            if cached_status is None or cached_status != status:
                if status is not None:
                    self.logger.debug(
                        f"Updating 'status' for {target_path}: {cached_status} -> {status}"
                    )
                    self.db.update_status(str(target_path), status)

            if (
                cached_file
                and cached_file["file_path"] == str(target_path)
                and cached_original_hash == original_file_hash
                and cached_source == current_source
                and cached_border_state == replace_border
                and cached_border_setting == self.border_setting
                and cached_custom_color == self.custom_color
            ):
                self.logger.debug(f"⏩ Skipping unchanged file: {file_path}")
                if webhook_run:
                    self.db.update_webhook_flag(str(target_path), True)
                return

        if not backup_dir:
            backup_dir = self.backup_dir
        try:
            if not backup_path.exists():
                shutil.copy2(file_path, backup_path)
                self.logger.debug(
                    f"Created backup of file {file_path} in {backup_dir}: {file_path}"
                )
            else:
                backed_up_hash = utils.hash_file(backup_path, self.logger)
                if original_file_hash != backed_up_hash:
                    shutil.copy2(file_path, backup_path)
                    self.logger.debug(
                        f"Updated backup at {backup_path}. Previous hash: {backed_up_hash}, New hash: {original_file_hash}"
                    )
                else:
                    self.logger.debug("Backup hashes match; no update needed")
        except Exception as e:
            self.logger.error(f"Error copying backup file {file_path}: {e}")

        if replace_border and self.border_setting:
            try:
                if self.border_setting.lower() == "remove":
                    final_image = self.border_replacerr.remove_border(file_path)
                    self.logger.info(f"Removed border on {file_path.name}")
                elif self.border_setting.lower() in {"custom", "black"}:
                    final_image = self.border_replacerr.replace_border(file_path)
                    self.logger.info(f"Replaced border on {file_path.name}")
                else:
                    self.logger.error(
                        f"Unsupported border setting: {self.border_setting}"
                    )
                    return

                temp_path = target_dir / f"temp_{new_file_name}"
                final_image.save(temp_path)
                file_path = temp_path
                file_hash = utils.hash_file(file_path, self.logger)
            except Exception as e:
                self.logger.error(f"Error processing border for {file_path}: {e}")
                file_hash = original_file_hash
        else:
            file_hash = original_file_hash
            if (
                target_path.exists()
                and cached_file
                and cached_file.get("border_replaced", False)
            ):
                try:
                    target_path.unlink()
                    self.logger.info(f"Deleted border-replaced file: {target_path}")
                except Exception as e:
                    self.logger.error(
                        f"Error deleting border-replaced file {target_path}: {e}"
                    )

        try:
            shutil.copy2(file_path, target_path)
            self.logger.info(f"Copied and renamed: {file_path} -> {target_path}")
            if cached_file:
                self.db.update_file(
                    file_hash=file_hash,
                    original_file_hash=original_file_hash,
                    source_path=current_source,
                    file_path=str(target_path),
                    border_replaced=replace_border,
                    border_setting=self.border_setting,
                    custom_color=self.custom_color,
                )
                self.logger.debug(f"Replaced cached file: {cached_file} -> {file_path}")
                if webhook_run:
                    self.db.update_webhook_flag(str(target_path), True)
            else:
                self.db.add_file(
                    file_path=str(target_path),
                    file_name=file_name_without_extension,
                    status=status,
                    has_episodes=has_episodes,
                    has_file=has_file,
                    media_type=media_type,
                    file_hash=file_hash,
                    original_file_hash=original_file_hash,
                    source_path=current_source,
                    border_replaced=replace_border,
                    border_setting=self.border_setting,
                    custom_color=self.custom_color,
                    webhook_run=webhook_run,
                )
                self.logger.debug(f"Adding new file to database cache: {target_path}")
        except Exception as e:
            self.logger.error(f"Error copying file {file_path}: {e}")

        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


    def setup_dirs(self, type, media_name, file_path, asset_folders, season_special="", separator=""):
        self.log_matched_file(type, media_name, str(file_path), season_special)
        target_dir = None
        backup_dir = None
        file_name_format = None
        if file_path.exists() and file_path.is_file():
            if asset_folders:
                target_dir = self.target_path / sanitize_filename(media_name)
                backup_dir = self.backup_dir / sanitize_filename(media_name)
                file_prefix = season_special if not season_special == "" else "poster"
                file_name_format = f"{file_prefix}{file_path.suffix}"
                if not target_dir.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.debug(f"Created directory -> '{target_dir}'")
                if not backup_dir.exists():
                    backup_dir.mkdir(parents=True, exist_ok=True)

            else:
                backup_dir = None
                target_dir = self.target_path
                file_name_format = sanitize_filename(f"{media_name}{separator}{season_special}{file_path.suffix}")
        return target_dir, backup_dir, file_name_format

    def copy_rename_files(
        self,
        matched_files: dict[str, dict],
        media_dict: dict[str, list],
        collections_dict: dict[str, list[str]],
        asset_folders: bool,
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
    ) -> None:
        show_dict_list = media_dict.get("shows", [])
        movies_dict_list = media_dict.get("movies", [])
        collections_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        matched_movies = len(matched_files.get("movies", []))
        matched_shows = len(matched_files.get("shows", []))
        matched_collections = len(matched_files.get("collections", []))
        total_matched_items = matched_movies + matched_shows + matched_collections
        with tqdm(
            total=total_matched_items, desc="Processing matched files"
        ) as progress_bar:
            processed_items = 0
            for key, items in matched_files.items():
                if key == "movies":
                    for file_path, data in items.items():
                        movie_data = data['match']
                        movie_title = movie_data['title']
                        target_dir, backup_dir, file_name_format = self.setup_dirs("movie", movie_title, file_path, asset_folders)

                        self._copy_file(
                            file_path,
                            key,
                            target_dir,
                            backup_dir,
                            file_name_format,
                            self.replace_border,
                            status=data.get("status", None),
                            has_file=data.get("has_file", None),
                            webhook_run=data.get("webhook_run", None),
                        )
                        processed_items += 1
                        progress_bar.update(1)
                        if job_id and cb:
                            progress = int((processed_items / total_matched_items) * 10)
                            cb(job_id, 80 + progress, ProgressState.IN_PROGRESS)

                if key == "collections":
                    for item in items:
                        file_path = item['file']
                        collection = item['match']
                        target_dir, backup_dir, file_name_format = self.setup_dirs("collection", collection, file_path, asset_folders)

                        self._copy_file(
                            file_path,
                            key,
                            target_dir,
                            backup_dir,
                            file_name_format,
                            self.replace_border,
                        )
                        processed_items += 1
                        progress_bar.update(1)
                        if job_id and cb:
                            progress = int((processed_items / total_matched_items) * 10)
                            cb(job_id, 80 + progress, ProgressState.IN_PROGRESS)

                if key == "shows":
                    for file_path, data in items.items():
                        show_data = data['match']
                        show_name = show_data['title']

                        match_season = re.match(r"(.+?) - Season (\d+)", file_path.stem)
                        match_specials = re.match(r"(.+?) - Specials", file_path.stem)

                        if match_season:
                            show_name_season = match_season.group(1)
                            season_num = int(match_season.group(2))
                            formatted_season_num = f"Season{season_num:02}"
                            target_dir, backup_dir, file_name_format = self.setup_dirs("season", show_name, file_path, asset_folders, formatted_season_num, "_")
                        elif match_specials:
                            show_name_specials = match_specials.group(1)
                            target_dir, backup_dir, file_name_format = self.setup_dirs("special", show_name, file_path, asset_folders, "Season00", "_")
                        else:
                            target_dir, backup_dir, file_name_format = self.setup_dirs("series", show_name, file_path, asset_folders)

                        self._copy_file(
                            file_path,
                            key,
                            target_dir,
                            backup_dir,
                            file_name_format,
                            self.replace_border,
                            status=data.get("status", None),
                            has_episodes=data.get("has_episodes", None),
                            webhook_run=data.get("webhook_run", None),
                        )
                        processed_items += 1
                        progress_bar.update(1)
                        if job_id and cb:
                            progress = int((processed_items / total_matched_items) * 10)
                            cb(job_id, 80 + progress, ProgressState.IN_PROGRESS)

    def handle_single_item(
        self,
        asset_type: str,
        instances: dict,
        single_item: dict,
        upload_to_plex: bool,
    ) -> dict[str, list] | None:
        self.logger.debug(pformat(single_item))
        media_dict = {"movies": [], "shows": []}
        instance_name = single_item.get("instance_name", "").lower()
        item_id = single_item.get("item_id")
        if not instance_name:
            self.logger.error("Instance name is missing for movie item")
            return None
        if not item_id or not isinstance(item_id, int):
            self.logger.error(
                f"Invalid item ID: {item_id} for instance: {instance_name}"
            )
            return None
        normalized_instances = {key.lower(): value for key, value in instances.items()}
        arr_instance = normalized_instances.get(instance_name)
        if not arr_instance:
            self.logger.error(f"Arr instance '{instance_name}' not found")
            return None
        try:
            items = (
                arr_instance.get_movie(item_id)
                if asset_type == "movie"
                else arr_instance.get_show(item_id)
            )
            if not items:
                self.logger.error(
                    f"{asset_type.capitalize()} with ID {item_id} not found in instance {instance_name}"
                )
                return None

            for item in items:
                if upload_to_plex:
                    item["webhook_run"] = True
                media_dict["movies" if asset_type == "movie" else "shows"].append(item)
            self.logger.debug(f"Fetched {asset_type}: {items}")
            return media_dict

        except Exception as e:
            self.logger.error(
                f"Error fetching {asset_type} from instance {instance_name}: {e}",
                exc_info=True,
            )
            return None

    def run(
        self,
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
        single_item: dict | None = None,
    ) -> dict | None:
        from DapsEX import utils

        try:
            unmatched_media_dict = {}
            unmatched_collections_dict = {}
            media_dict = {}
            collections_dict = {}
            self._log_banner()
            if single_item:
                self.logger.info("Run triggered for a single item via webhook")
                asset_type = single_item.get("type", "")
                combined_instances_dict = self.radarr_instances | self.sonarr_instances
                collections_dict = {"movies": [], "shows": []}

                media_dict = self.handle_single_item(
                    asset_type,
                    combined_instances_dict,
                    single_item,
                    self.upload_to_plex,
                )
                if not media_dict:
                    self.logger.error(
                        "Failed to create media dictionary for single item.. Exiting."
                    )
                    if job_id and cb:
                        cb(job_id, 95, ProgressState.IN_PROGRESS)
                    return
            else:
                if self.only_unmatched and not single_item:
                    self.logger.debug(
                        "Creating media and collections dict of unmatched items in library"
                    )
                    unmatched_media_dict = self.get_unmatched_media_dict()
                    unmatched_collections_dict = self.get_unmatched_collections_dict()
                else:
                    self.logger.debug(
                        "Creating media and collections dict of all items in library"
                    )

                media_dict = utils.get_combined_media_dict(
                    self.radarr_instances, self.sonarr_instances
                )
                collections_dict = utils.get_combined_collections_dict(
                    self.plex_instances
                )

            effective_media_dict = (
                unmatched_media_dict
                if self.only_unmatched and not single_item
                else media_dict
            )
            effective_collections_dict = (
                unmatched_collections_dict
                if self.only_unmatched and not single_item
                else collections_dict
            )

            if not any(effective_media_dict.values()) and not any(
                effective_collections_dict.values()
            ):
                self.logger.warning(
                    "Media and collections dictionaries are empty. Skipping processing."
                )
                if self.clean_assets:
                    self.logger.info(f"Cleaning orphan assets in {self.target_path}")
                    self.clean_asset_dir(media_dict, collections_dict)
                self.logger.info("Cleaning cache.")
                self.clean_cache()
                self.logger.info("Done.")
                if job_id and cb:
                    cb(job_id, 95, ProgressState.IN_PROGRESS)
                return

            self.logger.debug(
                "Media dict summary:\n%s", json.dumps(effective_media_dict, indent=4)
            )
            self.logger.debug(
                "Collections dict summary:\n%s",
                json.dumps(effective_collections_dict, indent=4),
            )

            if job_id and cb:
                cb(job_id, 10, ProgressState.IN_PROGRESS)
            source_files = self.get_source_files()
            self.logger.debug("Matching files with media")
            matched_files = self.match_files_with_media(
                source_files,
                effective_media_dict,
                effective_collections_dict,
                cb,
                job_id,
            )
            if self.asset_folders:
                self.logger.debug(
                    "-------------------------------------------------------"
                )
                self.logger.debug(f"Asset Folders: {self.asset_folders}")
                self.logger.debug("Starting file copying and renaming")
            else:
                self.logger.debug(
                    "-------------------------------------------------------"
                )
                self.logger.debug(f"Asset Folders: {self.asset_folders}")
                self.logger.debug("Starting file copying and renaming")

            self.copy_rename_files(
                matched_files,
                effective_media_dict,
                effective_collections_dict,
                self.asset_folders,
                cb,
                job_id,
            )

            if self.clean_assets and not single_item:
                self.logger.info(f"Cleaning orphan assets in {self.target_path}")
                self.clean_asset_dir(media_dict, collections_dict)
            self.logger.info("Cleaning cache.")
            self.clean_cache()
            self.logger.info("Done.")
            if job_id and cb:
                cb(job_id, 95, ProgressState.IN_PROGRESS)
            if single_item:
                return media_dict
        except Exception as e:
            self.logger.critical(f"Unexpected error occurred: {e}", exc_info=True)
            raise
