# TODO: add a way to clean asset directory when asset folders changes
import hashlib
import json
import logging
import re
import shutil
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
            self.db = Database()
            self.target_path = Path(payload.target_path)
            self.source_directories = payload.source_dirs
            self.asset_folders = payload.asset_folders
            self.clean_assets = payload.clean_assets
            self.upload_to_plex = payload.upload_to_plex
            self.match_alt = payload.match_alt
            self.replace_border = payload.replace_border
            self.border_color = payload.border_color if payload.border_color else None
            self.border_replacerr = BorderReplacerr(self.border_color)
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

    def _log_banner(self):
        self.logger.info("\n" + "#" * 80)
        self.logger.info("### New PosterRenamerr Run")
        self.logger.info("\n" + "#" * 80)

    def hash_file(self, file_path: Path) -> str:
        try:
            sha256_hash = hashlib.sha256()
            with file_path.open("rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.exception(f"Error hashing file {file_path}: {e}")
            raise e

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
            asset_files = (
                item for item in self.target_path.rglob("*") if item.is_file()
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
                        utils.remove_chars(collection)
                        for collection in collections_dict.get("movies", [])
                    )
                )
                .union(
                    set(
                        utils.remove_chars(collection)
                        for collection in collections_dict.get("shows", [])
                    )
                )
            )
            removed_asset_count = 0

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
                    if parent_dir == self.target_path:
                        self.logger.info(f"Removing orphaned asset file --> {item}")
                        item.unlink()
                        removed_asset_count += 1
                    else:
                        asset_title = utils.remove_chars(parent_dir.name)
                        if asset_title not in titles:
                            self._remove_directory(parent_dir)
                            removed_asset_count += 1
                else:
                    asset_pattern = re.search(r"^(.*?)(?:_.*)?$", item.stem)
                    if asset_pattern:
                        asset_title = utils.remove_chars(asset_pattern.group(1))
                        if asset_title not in titles:
                            self.logger.info(f"Removing orphaned asset file --> {item}")
                            item.unlink()
                            removed_asset_count += 1

            for dir_path in self.target_path.rglob("*"):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
            self.logger.info(
                f"Removed {removed_asset_count} items from asset directory."
            )

        except Exception as e:
            self.logger.error(f"Error cleaning assets: {e}")

    def _remove_directory(self, directory: Path):
        if directory.exists() and directory.is_dir():
            self.logger.info(f"Removing orphaned asset directory: {directory}")
            for sub_item in directory.iterdir():
                if sub_item:
                    sub_item.unlink()
            directory.rmdir()

    def get_source_files(self) -> dict[str, list[Path]]:
        source_directories = [Path(item) for item in self.source_directories]
        source_files = {}
        unique_files = set()

        for source_dir in source_directories:
            posters = list(source_dir.glob("*"))
            for poster in tqdm(
                posters, desc=f"Processing source files from {source_dir}"
            ):
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

        return source_files

    # TODO: add alternate titles for movies for matching
    # TODO: make alternate titles optional
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

        total_files = sum(len(files) for files in source_files.values())
        processed_files = 0

        for directory, files in source_files.items():
            for file in tqdm(files, desc=f"Matching files in {directory}"):
                name_without_extension = file.stem

                sanitized_name_without_extension = utils.remove_chars(
                    name_without_extension
                )
                sanitized_file_name_without_collection = (
                    sanitized_name_without_extension.removesuffix(" collection")
                )

                if (
                    sanitized_name_without_extension in unique_items
                    or sanitized_file_name_without_collection in unique_items
                ):
                    self.logger.debug(f"Skipping already matched file '{file}'")
                    continue

                year_match = re.search(r"\((\d{4})\)", file.stem)
                season_match = re.search(
                    r"\b- (season|specials)\b", file.stem, re.IGNORECASE
                )
                poster_file_year = year_match.group(1) if year_match else None
                matched = False

                if not poster_file_year and not season_match:
                    for collection_name in flattened_col_list:
                        sanitized_collection_name = utils.remove_chars(
                            collection_name
                        ).removesuffix(" collection")
                        if (
                            sanitized_file_name_without_collection
                            == sanitized_collection_name
                        ):
                            matched_files["collections"].append(file)
                            unique_items.add(sanitized_file_name_without_collection)
                            matched = True
                            self.logger.debug(
                                f"Matched collection poster for {collection_name} with {file}"
                            )
                            flattened_col_list.remove(collection_name)
                            break
                if matched:
                    continue

                if poster_file_year and not season_match:
                    for movie_data in movies_list_copy:
                        movie_title = movie_data.get("title", "")
                        movie_years = movie_data.get("years", [])
                        movie_status = movie_data.get("status", "")
                        movie_has_file = movie_data.get("has_file", None)
                        webhook_run = movie_data.get("webhook_run", None)
                        sanitized_movie_title = utils.remove_chars(
                            utils.strip_id(movie_title)
                        )
                        sanitized_movie_title_without_year = utils.remove_chars(
                            utils.strip_year(utils.strip_id(movie_title))
                        )
                        # self.logger.debug(
                        #     f"comparing file '{sanitized_name_without_extension}' with movie: '{sanitized_movie_title}'"
                        # )
                        if sanitized_name_without_extension == sanitized_movie_title:
                            matched = True
                            matched_files["movies"][file] = {
                                "has_file": movie_has_file,
                                "status": movie_status,
                            }
                            if webhook_run:
                                matched_files["movies"][file][
                                    "webhook_run"
                                ] = webhook_run
                            unique_items.add(sanitized_name_without_extension)
                            self.logger.debug(
                                f"Found exact match for movie: {movie_title} with {file}"
                            )
                            movies_list_copy.remove(movie_data)
                            break

                        elif movie_years:
                            for year in movie_years:
                                sanitized_movie_title_alternate_year = (
                                    f"{sanitized_movie_title_without_year} {year}"
                                )
                                if (
                                    sanitized_name_without_extension
                                    == sanitized_movie_title_alternate_year
                                ):
                                    matched = True
                                    matched_files["movies"][file] = {
                                        "has_file": movie_has_file,
                                        "status": movie_status,
                                    }
                                    if webhook_run:
                                        matched_files["movies"][file][
                                            "webhook_run"
                                        ] = webhook_run
                                    unique_items.add(sanitized_name_without_extension)
                                    self.logger.debug(
                                        f"Found year based match for movie: {movie_title} with {file}"
                                    )
                                    movies_list_copy.remove(movie_data)
                                    break
                        if matched:
                            break

                if matched:
                    continue

                if poster_file_year:
                    for show_data in shows_list_copy:
                        show_name = show_data.get("title", "")
                        show_year = re.search(r"\((\d{4})\)", show_name)
                        show_status = show_data.get("status", "")
                        show_seasons = show_data.get("seasons", [])
                        show_has_episodes = show_data.get("has_episodes", None)
                        webhook_run = show_data.get("webhook_run", None)
                        sanitized_show_name = utils.remove_chars(
                            utils.strip_id(show_name)
                        )
                        if self.match_alt or webhook_run:
                            alt_titles_clean = [
                                utils.remove_chars(alt)
                                for alt in show_data.get("alternate_titles", [])
                            ]
                            if show_year:
                                alt_titles_clean = [
                                    f"{alt} {show_year.group(1)}"
                                    for alt in alt_titles_clean
                                ]
                        else:
                            alt_titles_clean = []

                        matched_season = False
                        series_poster_matched = show_data.get(
                            "series_poster_matched", False
                        )

                        season_num_match = re.search(
                            r"- Season (\d+)", file.stem, re.IGNORECASE
                        )
                        if season_num_match:
                            season_num = int(season_num_match.group(1))
                            result = self._match_show_season(
                                sanitized_name_without_extension,
                                sanitized_show_name,
                                alt_titles_clean,
                            )
                            if isinstance(result, tuple):
                                main_match, alt_matches = result
                                for season in show_seasons[:]:
                                    season_str = season.get("season", "")
                                    season_str_match = re.match(
                                        r"season(\d+)", season_str
                                    )
                                    if season_str_match:
                                        media_season_num = int(
                                            season_str_match.group(1)
                                        )
                                        if season_num == media_season_num:
                                            season_has_episodes = season.get(
                                                "has_episodes", None
                                            )
                                            matched_files["shows"][file] = {
                                                "has_episodes": season_has_episodes
                                            }
                                            if webhook_run:
                                                matched_files["shows"][file][
                                                    "webhook_run"
                                                ] = webhook_run
                                            unique_items.add(main_match)
                                            if alt_matches:
                                                unique_items.update(alt_matches)
                                            show_seasons.remove(season)
                                            self.logger.debug(
                                                f"Matched season {season_num} for show: {show_name} with {file}"
                                            )
                                            matched_season = True
                                            break
                                if matched_season:
                                    if not show_seasons and series_poster_matched:
                                        shows_list_copy.remove(show_data)
                                        self.logger.debug(
                                            f"All seasons and series poster matched. Removed show: {show_name}"
                                        )
                                    break

                        if (
                            not matched_season
                            and sanitized_name_without_extension == sanitized_show_name
                        ):
                            matched_files["shows"][file] = {
                                "status": show_status,
                                "has_episodes": show_has_episodes,
                            }
                            if webhook_run:
                                matched_files["shows"][file][
                                    "webhook_run"
                                ] = webhook_run
                            unique_items.add(sanitized_name_without_extension)
                            if alt_titles_clean:
                                unique_items.update(alt_titles_clean)
                            self.logger.debug(
                                f"Matched series poster for show: {show_name} with {file}"
                            )
                            show_data["series_poster_matched"] = True
                            if not show_seasons and show_data["series_poster_matched"]:
                                shows_list_copy.remove(show_data)
                                self.logger.debug(
                                    f"All seasons and series poster matched. Removed show: {show_name}"
                                )
                            break
                        elif alt_titles_clean:
                            for alt_title in alt_titles_clean:
                                if sanitized_name_without_extension == alt_title:
                                    matched_files["shows"][file] = {
                                        "status": show_status,
                                        "has_episodes": show_has_episodes,
                                    }
                                    if webhook_run:
                                        matched_files["shows"][file][
                                            "webhook_run"
                                        ] = webhook_run
                                    unique_items.add(sanitized_show_name)
                                    unique_items.update(alt_titles_clean)
                                    self.logger.debug(
                                        f"Matched series poster for show: {show_name} with {file}"
                                    )
                                    show_data["series_poster_matched"] = True
                                    if (
                                        not show_seasons
                                        and show_data["series_poster_matched"]
                                    ):
                                        shows_list_copy.remove(show_data)
                                        self.logger.debug(
                                            f"All seasons and series poster matched. Removed show: {show_name}"
                                        )
                                    break

                        if not matched_season:
                            result = self._match_show_special(
                                sanitized_name_without_extension,
                                sanitized_show_name,
                                alt_titles_clean,
                            )
                            if isinstance(result, tuple):
                                main_match, alt_matches = result
                                for season in show_seasons:
                                    if "season00" in season.get("season", ""):
                                        season_has_episodes = season.get(
                                            "has_episodes", None
                                        )
                                        matched_files["shows"][file] = {
                                            "has_episodes": season_has_episodes
                                        }
                                        if webhook_run:
                                            matched_files["shows"][file][
                                                "webhook_run"
                                            ] = webhook_run
                                        unique_items.add(main_match)
                                        if alt_matches:
                                            unique_items.update(alt_matches)
                                        show_seasons.remove(season)
                                        self.logger.debug(
                                            f"Matched special season for show: {show_name}"
                                        )
                                        matched_season = True
                                        break
                            if matched_season:
                                if not show_seasons and series_poster_matched:
                                    shows_list_copy.remove(show_data)
                                    self.logger.debug(
                                        f"All seasons and series poster matched. Removed show: {show_name}"
                                    )
                                break

                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)

        self.logger.debug("Matched files summary:")
        self.logger.debug(pformat(matched_files))
        return matched_files

    def _match_show_season(
        self, file_name: str, show_name: str, alternate_titles: list
    ) -> bool | tuple[str, set[str]]:
        alt_titles = set()
        season_pattern = re.compile(
            rf"{re.escape(show_name)} season (\d+)", re.IGNORECASE
        )
        main_match = season_pattern.match(file_name)
        if main_match:
            season_num = main_match.group(1)
            main_title = f"{show_name} season {season_num}"
            for alt_title in alternate_titles:
                alt_titles.add(f"{alt_title} season {season_num}")
            # self.logger.debug(
            #     f"Matched main title: {main_title}, Alt titles: {alt_titles}"
            # )
            return main_title, alt_titles
        else:
            for alt_title in alternate_titles:
                season_pattern_alt = re.compile(
                    rf"{re.escape(alt_title)} season (\d+)",
                    re.IGNORECASE,
                )
                alt_match = season_pattern_alt.match(file_name)
                if alt_match:
                    season_num = alt_match.group(1)
                    main_title = f"{show_name} season {season_num}"
                    for alt_title in alternate_titles:
                        alt_titles.add(f"{alt_title} season {season_num}")
                    # self.logger.debug(
                    #     f"Matched alt title: {alt_match.group()}, Main title: {main_title}, Alt titles: {alt_titles}"
                    # )
                    return main_title, alt_titles
        return False

    def _match_show_special(
        self, file_name: str, show_name: str, alternate_titles: list
    ) -> bool | tuple[str, set[str]]:
        alt_titles = set()
        specials_pattern = re.compile(
            rf"{re.escape(show_name)} specials", re.IGNORECASE
        )
        main_match = specials_pattern.match(file_name)
        if main_match:
            main_title = f"{show_name} specials"
            for alt_title in alternate_titles:
                alt_titles.add(f"{alt_title} specials")
            # self.logger.debug(
            #     f"Matched main title: {main_title}, Alt titles: {alt_titles}"
            # )
            return main_title, alt_titles

        else:
            for alt_title in alternate_titles:
                specials_pattern_alt = re.compile(
                    rf"{re.escape(alt_title)} specials",
                    re.IGNORECASE,
                )
                alt_match = specials_pattern_alt.match(file_name)
                if alt_match:
                    main_title = f"{show_name} specials"
                    for alt_title in alternate_titles:
                        alt_titles.add(f"{alt_title} specials")
                    # self.logger.debug(
                    #     f"Matched alt title: {alt_match.group()}, Main title: {main_title}, Alt titles: {alt_titles}"
                    # )
                    return main_title, alt_titles
        return False

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

    # TODO: fix looping with alternate title matching
    def _copy_file(
        self,
        file_path: Path,
        media_type: str,
        target_dir: Path,
        new_file_name: str,
        replace_border: bool = False,
        status: str | None = None,
        has_episodes: bool | None = None,
        has_file: bool | None = None,
        webhook_run: bool | None = None,
    ) -> None:
        temp_path = None
        target_path = target_dir / new_file_name
        file_name_without_extension = target_path.stem
        original_file_hash = self.hash_file(file_path)
        cached_file = self.db.get_cached_file(str(target_path))
        current_source = str(file_path)

        if target_path.exists() and cached_file:
            cached_hash = cached_file["file_hash"]
            cached_original_hash = cached_file["original_file_hash"]
            cached_source = cached_file["source_path"]
            cached_border_state = cached_file.get("border_replaced", 0)
            cached_border_color = cached_file.get("border_color", None)
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
            self.logger.debug(f"Cached border color: {cached_border_color}")
            self.logger.debug(f"Current border color: {self.border_color}")
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
                    self.db.update_has_episodes(
                        str(target_path), has_episodes, self.logger
                    )

            if cached_has_file is None or cached_has_file != has_file:
                if has_file is not None:
                    self.logger.debug(
                        f"Updating 'has_file' for {target_path}: {cached_has_file} -> {has_file}"
                    )
                    self.db.update_has_file(str(target_path), has_file, self.logger)

            if cached_status is None or cached_status != status:
                if status is not None:
                    self.logger.debug(
                        f"Updating 'status' for {target_path}: {cached_status} -> {status}"
                    )
                    self.db.update_status(str(target_path), status, self.logger)

            if (
                cached_file
                and cached_file["file_path"] == str(target_path)
                and cached_original_hash == original_file_hash
                and cached_source == current_source
                and cached_border_state == replace_border
                and cached_border_color == self.border_color
            ):
                self.logger.debug(f"⏩ Skipping unchanged file: {file_path}")
                if webhook_run:
                    self.db.update_webhook_flag(str(target_path), self.logger, True)
                return

        if replace_border and self.border_color:
            supported_colors = [
                "black",
                "red",
                "green",
                "blue",
                "yellow",
                "cyan",
                "magenta",
                "gray",
            ]
            try:
                if self.border_color.lower() == "remove":
                    final_image = self.border_replacerr.remove_border(file_path)
                    self.logger.info(f"Removed border on {file_path.name}")
                elif self.border_color.lower() in supported_colors:
                    final_image = self.border_replacerr.replace_border(file_path)
                    self.logger.info(f"Replaced border on {file_path.name}")
                else:
                    self.logger.error(f"Unsupported border color: {self.border_color}")
                    return

                temp_path = target_dir / f"temp_{new_file_name}"
                final_image.save(temp_path)
                file_path = temp_path
                file_hash = self.hash_file(file_path)
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
                    self.logger,
                    file_hash,
                    original_file_hash,
                    current_source,
                    str(target_path),
                    border_replaced=replace_border,
                    border_color=self.border_color,
                )
                self.logger.debug(f"Replaced cached file: {cached_file} -> {file_path}")
                if webhook_run:
                    self.db.update_webhook_flag(str(target_path), self.logger, True)
            else:
                self.db.add_file(
                    self.logger,
                    str(target_path),
                    file_name_without_extension,
                    status,
                    has_episodes,
                    has_file,
                    media_type,
                    file_hash,
                    original_file_hash,
                    current_source,
                    border_replaced=replace_border,
                    border_color=self.border_color,
                    webhook_run=webhook_run,
                )
                self.logger.debug(f"Adding new file to database cache: {target_path}")
        except Exception as e:
            self.logger.error(f"Error copying file {file_path}: {e}")

        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    def copy_rename_files(
        self,
        matched_files: dict[str, dict],
        media_dict: dict[str, list],
        collections_dict: dict[str, list[str]],
        asset_folders: bool,
    ) -> None:
        show_dict_list = media_dict.get("shows", [])
        movies_dict_list = media_dict.get("movies", [])
        collections_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        for key, items in matched_files.items():
            if key == "movies":
                for file_path, data in items.items():
                    movie_result = self._handle_movie(
                        file_path, movies_dict_list, asset_folders
                    )
                    if not movie_result:
                        continue

                    if isinstance(movie_result, tuple):
                        target_dir, file_name_format = movie_result
                        if not target_dir.exists():
                            target_dir.mkdir(parents=True, exist_ok=True)
                            self.logger.debug(f"Created directory -> '{target_dir}'")
                    else:
                        target_dir = self.target_path
                        file_name_format = sanitize_filename(movie_result)

                    self._copy_file(
                        file_path,
                        key,
                        target_dir,
                        file_name_format,
                        self.replace_border,
                        status=data.get("status", None),
                        has_file=data.get("has_file", None),
                        webhook_run=data.get("webhook_run", None),
                    )

            if key == "collections":
                for item in items:
                    collection_result = self._handle_collections(
                        item, collections_list, asset_folders
                    )
                    if not collection_result:
                        continue
                    if isinstance(collection_result, tuple):
                        target_dir, file_name_format = collection_result
                        if not target_dir.exists():
                            target_dir.mkdir(parents=True, exist_ok=True)
                            self.logger.debug(f"Created directory -> '{target_dir}'")
                    else:
                        target_dir = self.target_path
                        file_name_format = sanitize_filename(collection_result)

                    self._copy_file(
                        item,
                        key,
                        target_dir,
                        file_name_format,
                        self.replace_border,
                    )

            if key == "shows":
                for file_path, data in items.items():
                    show_result = self._handle_series(
                        file_path, show_dict_list, asset_folders
                    )
                    if not show_result:
                        continue
                    if isinstance(show_result, tuple):
                        target_dir, file_name_format = show_result
                        if not target_dir.exists():
                            target_dir.mkdir(parents=True, exist_ok=True)
                            self.logger.debug(f"Created directory -> '{target_dir}'")
                    else:
                        target_dir = self.target_path
                        file_name_format = sanitize_filename(show_result)

                    self._copy_file(
                        file_path,
                        key,
                        target_dir,
                        file_name_format,
                        self.replace_border,
                        status=data.get("status", None),
                        has_episodes=data.get("has_episodes", None),
                        webhook_run=data.get("webhook_run", None),
                    )

    def _handle_movie(
        self, item: Path, movies_list_dict: list[dict], asset_folders: bool
    ) -> str | tuple[Path, str] | None:
        matched_file = utils.remove_chars(item.stem)

        for item_dict in movies_list_dict:
            movie_title = item_dict.get("title", "")
            movie_years = item_dict.get("years", [])

            movie_clean = utils.remove_chars((utils.strip_id(movie_title)))
            movie_clean_without_year = utils.remove_chars(
                utils.strip_year(utils.strip_id(movie_title))
            )

            if matched_file == movie_clean:
                self.log_matched_file("movie", movie_title, str(item))
                if item.exists() and item.is_file():
                    if asset_folders:
                        target_dir = self.target_path / sanitize_filename(movie_title)
                        file_name_format = f"poster{item.suffix}"
                        return target_dir, file_name_format
                    else:
                        return f"{movie_title}{item.suffix}"

            for year in movie_years:
                movie_title_alternate_year = f"{movie_clean_without_year} {year}"
                if matched_file == movie_title_alternate_year:
                    self.log_matched_file("movie", movie_title, str(item))
                    if item.exists() and item.is_file():
                        if asset_folders:
                            target_dir = self.target_path / sanitize_filename(
                                movie_title
                            )
                            file_name_format = f"poster{item.suffix}"
                            return target_dir, file_name_format
                        else:
                            return f"{movie_title}{item.suffix}"
        return None

    def _handle_collections(
        self, item: Path, collections_list: list[str], asset_folders: bool
    ) -> str | tuple[Path, str] | None:
        collection_name = utils.remove_chars(item.stem).removesuffix(" collection")
        for collection in collections_list:
            collection_clean = utils.remove_chars(collection).removesuffix(
                " collection"
            )
            if collection_name == collection_clean:
                self.log_matched_file("collection", collection, str(item))
                if item.exists() and item.is_file():
                    if asset_folders:
                        target_dir = self.target_path / sanitize_filename(collection)
                        file_name_format = f"poster{item.suffix}"
                        return target_dir, file_name_format
                    else:
                        return f"{collection}{item.suffix}"
        return None

    def _handle_series(
        self,
        item: Path,
        show_list_dict: list[dict],
        asset_folders,
    ) -> str | tuple[Path, str] | None:
        match_season = re.match(r"(.+?) - Season (\d+)", item.stem)
        match_specials = re.match(r"(.+?) - Specials", item.stem)

        def clean_show_name(show: str) -> str:
            return utils.remove_chars(utils.strip_id(show))

        def is_match(file_name, media_dict_name, alt_titles_clean):
            year = re.search(r"\((\d{4})\)", media_dict_name)
            media_dict_name_clean = clean_show_name(media_dict_name)
            file_name_clean = utils.remove_chars(file_name)

            if media_dict_name_clean == file_name_clean:
                return True
            else:
                for title in alt_titles_clean:
                    alt_title_with_year = (
                        f"{title} {year.group(1) if year else ''}".strip()
                    )
                    if alt_title_with_year == file_name_clean:
                        return True
            return False

        if match_season:
            show_name_season = match_season.group(1)
            season_num = int(match_season.group(2))
            formatted_season_num = f"Season{season_num:02}"
            for item_dict in show_list_dict:
                alt_titles_clean = [
                    utils.remove_chars(alt)
                    for alt in item_dict.get("alternate_titles", [])
                ]
                show_name = item_dict.get("title", "")
                match = is_match(show_name_season, show_name, alt_titles_clean)
                if match:
                    self.log_matched_file(
                        "season", show_name, str(item), formatted_season_num
                    )
                    if item.exists() and item.is_file():
                        if asset_folders:
                            target_dir = self.target_path / sanitize_filename(show_name)
                            file_name_format = f"{formatted_season_num}{item.suffix}"
                            return target_dir, file_name_format
                        else:
                            return f"{show_name}_{formatted_season_num}{item.suffix}"
            return None
        elif match_specials:
            show_name_specials = match_specials.group(1)
            for item_dict in show_list_dict:
                alt_titles_clean = [
                    utils.remove_chars(alt)
                    for alt in item_dict.get("alternate_titles", [])
                ]
                show_name = item_dict.get("title", "")
                match = is_match(show_name_specials, show_name, alt_titles_clean)
                if match:
                    self.log_matched_file("special", show_name, str(item), "Season00")
                    if item.exists() and item.is_file():
                        if asset_folders:
                            target_dir = self.target_path / sanitize_filename(show_name)
                            file_name_format = f"Season00{item.suffix}"
                            return target_dir, file_name_format
                        else:
                            return f"{show_name}_Season00{item.suffix}"
            return None
        else:
            show_name_normal = item.stem
            for item_dict in show_list_dict:
                alt_titles_clean = [
                    utils.remove_chars(alt)
                    for alt in item_dict.get("alternate_titles", [])
                ]
                show_name = item_dict.get("title", "")
                match = is_match(show_name_normal, show_name, alt_titles_clean)
                if match:
                    self.log_matched_file("series", show_name, str(item))
                    if item.exists() and item.is_file():
                        if asset_folders:
                            target_dir = self.target_path / sanitize_filename(show_name)
                            file_name_format = f"poster{item.suffix}"
                            return target_dir, file_name_format
                        else:
                            return f"{show_name}{item.suffix}"
        return None

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
                        "Failed to create media dictonary for single item.. Exiting."
                    )
                    return
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
            self.logger.debug(
                "Media dict summary:\n%s", json.dumps(media_dict, indent=4)
            )
            self.logger.debug(
                "Collections dict summary:\n%s", json.dumps(collections_dict, indent=4)
            )
            if job_id and cb:
                cb(job_id, 10, ProgressState.IN_PROGRESS)
            source_files = self.get_source_files()
            self.logger.debug("Matching files with media")
            matched_files = self.match_files_with_media(
                source_files, media_dict, collections_dict, cb, job_id
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
                matched_files, media_dict, collections_dict, self.asset_folders
            )

            if job_id and cb:
                cb(job_id, 100, ProgressState.COMPLETED)
            if self.clean_assets and not single_item:
                self.logger.info(f"Cleaning orphan assets in {self.target_path}")
                self.clean_asset_dir(media_dict, collections_dict)
            self.clean_cache()
            if single_item:
                return media_dict
        except Exception as e:
            self.logger.critical(f"Unexpected error occured: {e}", exc_info=True)
            raise
