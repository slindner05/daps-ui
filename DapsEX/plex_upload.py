import json
import logging
import re
import time
from pathlib import Path
from pprint import pformat

from DapsEX import utils
from DapsEX.database_cache import Database
from DapsEX.logger import init_logger
from DapsEX.media import Radarr, Server, Sonarr


class PlexUploaderr:
    def __init__(
        self,
        payload,
        webhook_item: dict | None = None,
        media_dict: dict | None = None,
    ) -> None:
        from DapsEX.settings import Settings

        self.logger = logging.getLogger("PlexUploaderr")
        try:
            log_dir = Path(Settings.LOG_DIR.value) / Settings.PLEX_UPLOADERR.value
            init_logger(
                self.logger,
                log_dir,
                Settings.PLEX_UPLOADERR.value,
                payload.log_level if payload.log_level else logging.INFO,
            )
            self.db = Database()
            self.asset_folders = payload.asset_folders
            self.reapply_posters = payload.reapply_posters
            self.plex_instances = utils.create_plex_instances(
                payload, Server, self.logger
            )
            self.radarr_instances, self.sonarr_instances = utils.create_arr_instances(
                payload, Radarr, Sonarr, self.logger
            )
            self.webhook_item = webhook_item
            self.media_dict = media_dict
        except Exception as e:
            self.logger.exception("Failed to initialize PlexUploaderr")
            raise e

    def _log_banner(self):
        self.logger.info("\n" + "#" * 80)
        self.logger.info("### New PlexUplaoaderr Run")
        self.logger.info("\n" + "#" * 80)

    def add_poster_to_plex(
        self,
        plex_media_objects: list,
        file_path: str,
        show_title: str | None = None,
    ):
        try:
            libraries = set()
            for item in plex_media_objects:
                try:
                    library = getattr(item, "librarySectionTitle", "Unknown Library")
                    item.uploadPoster(filepath=file_path)
                    libraries.add(library)
                    if show_title:
                        self.logger.info(
                            f"Successfully uploaded poster for show '{show_title}' item '{item.title}' to library '{library}'"
                        )
                    else:
                        self.logger.info(
                            f"Uploaded poster for item '{item.title}' to library '{library}'"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to upload poster for item '{item.title}': {e}"
                    )
            self.db.update_uploaded_to_libraries(
                file_path, list(libraries), self.logger
            )
        except Exception as e:
            if show_title:
                self.logger.error(
                    f"Error uploading poster for '{show_title}', item {plex_media_objects[0].title}"
                )
            else:
                self.logger.error(
                    f"Error uploading poster for item: {plex_media_objects[0].title}: {e}"
                )

    def process_files(
        self,
        processed_files: set,
        cached_items: dict,
        plex_dict: dict,
        item_type: str,
    ):
        for file_path, file_info in cached_items.items():

            if file_path in processed_files:
                continue

            if self.asset_folders:
                asset_file_path = Path(file_path)
                file_name = utils.remove_chars(asset_file_path.parent.name)
            else:
                file_name = utils.remove_chars(file_info["file_name"])
            self.logger.debug(f"Processing cached {item_type} file: '{file_path}'")
            uploaded_to_libraries = file_info.get("uploaded_to_libraries", [])
            item_matches = self.find_match(
                file_name, plex_dict[item_type], uploaded_to_libraries
            )
            if not item_matches:
                self.logger.debug(
                    "All libraries skipped for file item, no further processing."
                )
                processed_files.add(file_path)
                continue

            for library_name, item in item_matches:
                self.logger.debug(
                    f"Match found for file '{file_path}' -> Plex {item_type} '{item.title}' in library '{library_name}'"
                )
            item_list = [item for _, item in item_matches]
            if file_path not in processed_files:
                processed_files.add(file_path)
                self.add_poster_to_plex(item_list, file_path)

    def process_season_files(
        self,
        processed_files: set,
        plex_show_dict: dict,
        file_path: str,
        file_info: dict,
    ) -> bool:
        if self.asset_folders:
            season_match = re.match(r"^Season(\d{2})", file_info["file_name"])
        else:
            season_match = re.match(
                r"^(.*\s\(\d{4}\)\s.*)_Season(\d{2}).*$", file_info["file_name"]
            )
        if not season_match:
            return False

        if self.asset_folders:
            asset_file_path = Path(file_path)
            file_name = utils.remove_chars(asset_file_path.parent.name)
            season_num = int(season_match.group(1))
        else:
            file_name = utils.remove_chars(f"{season_match.group(1)}")
            season_num = int(season_match.group(2))
        self.logger.debug(f"Processing cached season file: '{file_path}'")
        uploaded_to_libraries = file_info.get("uploaded_to_libraries", [])
        show_matches = self.find_match(
            file_name, plex_show_dict["show"], uploaded_to_libraries
        )

        if not show_matches:
            self.logger.debug(
                "All libraries skipped for season, no further processing."
            )
            processed_files.add(file_path)
            return True

        for library_name, show in show_matches:
            self.logger.debug(
                f"Match found for file '{file_path}' -> Plex show '{show.title}' in library '{library_name}'"
            )
        matching_seasons = [
            (show.title, season)
            for _, show in show_matches
            for season in show.seasons()
            if season.index == season_num
        ]

        if matching_seasons:
            first_show_title, first_season = matching_seasons[0]
            self.logger.debug(
                f"Match found for Season {first_season} for Show {first_show_title}"
            )

            seasons_only = [season for _, season in matching_seasons]
            if file_path not in processed_files:
                processed_files.add(file_path)
                self.add_poster_to_plex(seasons_only, file_path, first_show_title)
        else:
            for _, show in show_matches:
                self.logger.warning(
                    f"Season {season_num} not found for show '{show.title}'"
                )
        return True

    def find_match(
        self,
        file_name: str,
        plex_items: dict,
        uploaded_to_libraries: list,
    ):
        matches = []

        for library_name, item_dict in plex_items.items():
            if library_name in uploaded_to_libraries:
                self.logger.debug(
                    f"File already uploaded to library '{library_name}', skipping."
                )
                continue

            for title, plex_object in item_dict.items():
                item_name = utils.remove_chars(title)
                # self.logger.debug(
                #     f"Comparing file: '{file_name}' with item '{item_name}'"
                # )
                if file_name == item_name:
                    matches.append((library_name, plex_object))

        return matches

    def upload_poster(
        self,
        cached_files: dict,
        plex_movie_dict: dict | None = None,
        plex_show_dict: dict | None = None,
    ) -> None:

        def filter_cached_files_by_type(cached_files, media_type):
            filtered_files = {
                file_path: file_info
                for file_path, file_info in cached_files.items()
                if file_info.get("media_type") == media_type
            }
            return filtered_files if filtered_files else {}

        processed_files = set()
        movies_only = filter_cached_files_by_type(cached_files, "movies")
        collections_only = filter_cached_files_by_type(cached_files, "collections")
        shows_only = filter_cached_files_by_type(cached_files, "shows")
        combined_collections = {"collections": {}}

        if plex_movie_dict:
            for library_name, collections_dict in plex_movie_dict.get(
                "collections", {}
            ).items():
                if library_name not in combined_collections:
                    combined_collections["collections"][library_name] = {}
                combined_collections["collections"][library_name].update(
                    collections_dict
                )

        if plex_show_dict:
            for library_name, collections_dict in plex_show_dict.get(
                "collections", {}
            ).items():
                if library_name not in combined_collections:
                    combined_collections["collections"][library_name] = {}
                combined_collections["collections"][library_name].update(
                    collections_dict
                )

        if plex_movie_dict:
            self.process_files(
                processed_files,
                movies_only,
                plex_movie_dict,
                "movie",
            )

        if plex_show_dict:
            for file_path, file_info in shows_only.items():
                if file_path in processed_files:
                    continue

                is_season = self.process_season_files(
                    processed_files,
                    plex_show_dict,
                    file_path,
                    file_info,
                )

                if not is_season and file_path not in processed_files:
                    self.process_files(
                        processed_files,
                        {file_path: file_info},
                        plex_show_dict,
                        "show",
                    )

        if combined_collections:
            self.process_files(
                processed_files,
                collections_only,
                combined_collections,
                "collections",
            )

    def convert_plex_dict_titles_to_paths(
        self,
        plex_movie_dict: dict | None = None,
        plex_show_dict: dict | None = None,
    ) -> tuple[dict, dict] | dict:

        updated_movie_dict = {}
        updated_show_dict = {}

        if plex_show_dict:
            for library_title, show_dict in plex_show_dict.get("show", {}).items():
                updated_show_dict[library_title] = {}
                for plex_title, show in show_dict.items():
                    try:
                        first_season = show.seasons()[0]
                        first_episode = first_season.episodes()[0]
                        first_media = first_episode.media[0]
                        first_part = first_media.parts[0]
                        item_path = Path(first_part.file)
                        new_title = item_path.parent.parent.name
                        updated_show_dict[library_title][new_title] = show
                    except Exception as e:
                        self.logger.warning(
                            f"Could not determine path for show: '{plex_title}' in library '{library_title}'. Error: {e}"
                        )

        if plex_movie_dict:
            for library_title, movie_dict in plex_movie_dict.get("movie", {}).items():
                updated_movie_dict[library_title] = {}
                for plex_title, movie in movie_dict.items():
                    try:
                        file_part = next(
                            (
                                part.file
                                for media in movie.media
                                for part in media.parts
                                if part.file
                            ),
                            None,
                        )
                        if not file_part:
                            raise ValueError(
                                f"No valid file part found for {movie.title}"
                            )
                        item_path = Path(file_part)
                        new_title = item_path.parent.name
                        updated_movie_dict[library_title][new_title] = movie
                    except Exception as e:
                        self.logger.warning(
                            f"Could not determine path for movie: '{plex_title}' in library '{library_title}'. Error: {e}"
                        )

        if updated_movie_dict and updated_show_dict:
            return updated_movie_dict, updated_show_dict
        elif updated_movie_dict:
            return updated_movie_dict
        elif updated_show_dict:
            return updated_show_dict
        else:
            return {}

    def search_recently_added_for_items(
        self,
        media_type: str,
        media_title: str,
        webhook_cached_files: dict,
    ):
        max_retries = 10
        retry_delay = 30
        found_item = False
        plex_media_dict = {}
        filtered_movies = {media_type: {}, "collections": {}}
        for attempt in range(1, max_retries + 1):
            self.logger.info(
                f"Attempt {attempt}/{max_retries}: Searching recently added items."
            )
            for name, server in self.plex_instances.items():
                recently_added_dict = server.fetch_recently_added(
                    media_type, self.logger
                )
                if not recently_added_dict:
                    continue

                key = "all_movies" if media_type == "movie" else "all_shows"
                plex_media_dict[name] = {key: recently_added_dict}

                for server_name, item_dict in plex_media_dict.items():
                    updated_item_dict = self.convert_plex_dict_titles_to_paths(
                        plex_movie_dict=(
                            item_dict[key] if media_type == "movie" else None
                        ),
                        plex_show_dict=(
                            item_dict[key] if media_type == "show" else None
                        ),
                    )
                    if not isinstance(updated_item_dict, dict):
                        self.logger.error(
                            f"Expected a dictionary, but got {type(updated_item_dict)}"
                        )
                        continue

                    for library_name, items in updated_item_dict.items():
                        for item_title, item_obj in items.items():
                            if item_title == media_title:
                                found_item = True
                                filtered_movies[media_type].setdefault(
                                    library_name, {}
                                )[item_title] = item_obj
                                self.logger.info(
                                    f"Found '{item_title}' in library '{library_name}'"
                                )

                    if found_item:
                        item_dict[key] = filtered_movies
                        self.logger.debug(pformat(plex_media_dict))
                        self.logger.info(
                            f"Uploading posters for Plex instance: {server_name}"
                        )
                        self.upload_poster(
                            webhook_cached_files,
                            plex_movie_dict=(
                                item_dict["all_movies"]
                                if media_type == "movie"
                                else None
                            ),
                            plex_show_dict=(
                                item_dict["all_shows"] if media_type == "show" else None
                            ),
                        )
                        break

                if found_item:
                    self.logger.info("Item found successfully. Exiting search.")
                    return

                if not found_item and attempt < max_retries:
                    self.logger.info(
                        f"Item not found. Retrying in {retry_delay} seconds."
                    )
                    time.sleep(retry_delay)
                else:
                    self.logger.warning(
                        f"Item '{media_title}' not found after {max_retries} retries."
                    )

    def upload_posters_full(self):
        plex_media_dict = {}

        self._log_banner()
        if self.reapply_posters:
            self.db.clear_uploaded_to_libraries_data(self.logger)
            self.logger.info(
                "Reapply posters is enabled. Clearing uploaded_to_libraries data and re-uploading them to plex."
            )
        else:
            self.logger.info("Reapply posters is disabled. No action taken.")

        cached_files = self.db.return_all_files()
        self.logger.debug(
            "Attempting to update current has_file and has_episodes values."
        )
        self.update_cached_files(cached_files)

        self.logger.debug(json.dumps(cached_files, indent=4))
        valid_files = {}
        for file_path, file_info in cached_files.items():
            if (
                file_info.get("has_episodes") == 1
                or file_info.get("has_file") == 1
                or file_info.get("media_type") == "collections"
            ):
                valid_files[file_path] = file_info
            else:
                self.logger.debug(
                    f"Skipping {file_path} because it does not meet the criteria: "
                    f"has_episodes={file_info.get('has_episodes')}, "
                    f"has_file={file_info.get('has_file')}"
                )

        if valid_files:
            self.logger.debug(f"Total cached files: {len(cached_files)}")
            self.logger.debug(f"Valid files to process: {len(valid_files)}")
            for name, server in self.plex_instances.items():
                try:
                    plex_movie_dict, plex_show_dict = server.get_media()
                    plex_media_dict[name] = {
                        "all_movies": plex_movie_dict,
                        "all_shows": plex_show_dict,
                    }
                except Exception as e:
                    self.logger.error(
                        f"Error retrieving media for Plex instance '{name}': {e}"
                    )
                    plex_media_dict[name] = {"all_movies": {}, "all_shows": {}}

            for server_name, item_dict in plex_media_dict.items():
                updated_movie_dict, updated_show_dict = (
                    self.convert_plex_dict_titles_to_paths(
                        item_dict["all_movies"], item_dict["all_shows"]
                    )
                )
                item_dict["all_movies"]["movie"] = updated_movie_dict
                item_dict["all_shows"]["show"] = updated_show_dict
                self.logger.debug("Updated plex media dict:")
                self.logger.debug(pformat(item_dict))
                self.logger.info(f"Uploading posters for Plex instance: {server_name}")
                self.upload_poster(
                    valid_files,
                    item_dict["all_movies"],
                    item_dict["all_shows"],
                )
        else:
            self.logger.info("No new files to upload to Plex")

    def update_cached_files(self, cached_files: dict):
        media_dict = utils.get_combined_media_dict(
            self.radarr_instances, self.sonarr_instances
        )
        movies_lookup = {
            movie["title"].lower(): movie["has_file"]
            for movie in media_dict.get("movies", [])
        }
        # self.logger.debug("Movies lookup:")
        # self.logger.debug(pformat(movies_lookup))

        shows_lookup = {}
        for show in media_dict.get("shows", []):
            show_title = show["title"].lower()
            shows_lookup[show_title] = {
                "has_episodes": show.get("has_episodes", False),
                "seasons": {
                    season["season"].lower(): season.get("has_episodes", False)
                    for season in show.get("seasons", [])
                },
            }
        # self.logger.debug("Shows lookup:")
        # self.logger.debug(pformat(shows_lookup))

        for file_path, cached_item in cached_files.items():
            if self.asset_folders:
                title = Path(file_path).parent.name.lower()
                season_pattern = re.match(r"(Season\d{2})", cached_item["file_name"])
            else:
                title = cached_item.get("file_name").lower()
                season_pattern = re.match(
                    r".*_(Season\d{2})$", cached_item["file_name"]
                )

            media_type = cached_item.get("media_type")

            if media_type == "collections":
                continue

            if media_type == "movies":
                cached_has_file = bool(cached_item.get("has_file", 0))
                if title in movies_lookup:
                    current_has_file = movies_lookup[title]
                    if current_has_file != cached_has_file:
                        cached_item["has_file"] = int(current_has_file)
                        self.db.update_has_file(
                            file_path, current_has_file, self.logger
                        )
                else:
                    self.logger.warning(
                        f"Movie title: '{title}' not found in movies lookup when processing '{file_path}'."
                    )

            if media_type == "shows":
                cached_has_episodes = bool(cached_item.get("has_episodes"))
                if season_pattern:
                    season = season_pattern.group(1).lower()
                    if title in shows_lookup:
                        lookup_entry = shows_lookup[title]
                        current_season_has_episodes = lookup_entry["seasons"].get(
                            season, False
                        )

                        if current_season_has_episodes != cached_has_episodes:
                            cached_item["has_episodes"] = int(
                                current_season_has_episodes
                            )
                            self.db.update_has_episodes(
                                file_path, current_season_has_episodes, self.logger
                            )
                    else:
                        self.logger.warning(
                            f"Show title: '{title}' not found in shows lookup when processing '{file_path}'."
                        )
                else:
                    if title in shows_lookup:
                        current_series_has_episodes = shows_lookup[title][
                            "has_episodes"
                        ]
                        if current_series_has_episodes != cached_has_episodes:
                            cached_item["has_episodes"] = int(
                                current_series_has_episodes
                            )
                            self.db.update_has_episodes(
                                file_path, current_series_has_episodes, self.logger
                            )
                    else:
                        self.logger.warning(
                            f"Show title: '{title}' not found in shows lookup when processing '{file_path}'."
                        )

    def upload_posters_webhook(
        self,
    ):
        self._log_banner()
        if self.reapply_posters:
            self.db.clear_uploaded_to_libraries_data(self.logger, webhook_run=True)
            self.logger.info(
                "Reapply posters is enabled. Clearing uploaded_to_libraries data for webhook-run items "
                "and re-uploading them to Plex if they exist."
            )
        else:
            self.logger.info("Reapply posters is disabled. No action taken.")

        if not self.webhook_item:
            self.logger.error("Webhook item data missing. Exiting.")
            raise ValueError

        if not self.media_dict:
            self.logger.error("Media dict item data missing. Exiting.")
            raise ValueError

        plex_media_dict = {}
        item_type = self.webhook_item.get("type", None)
        if item_type == "movie":
            item = next((item for item in self.media_dict.get("movies", [])))
        else:
            item_type = "show"
            item = next((item for item in self.media_dict.get("shows", [])))
        item_title = item["title"]

        webhook_cached_files = self.db.return_all_files(webhook_run=True)
        self.logger.debug(
            "Attempting to update current has_file and has_episodes values."
        )
        self.update_cached_files(webhook_cached_files)
        self.logger.debug(json.dumps(webhook_cached_files, indent=4))
        for file_path in webhook_cached_files.keys():
            self.db.update_webhook_flag(file_path, self.logger)

        if webhook_cached_files:
            for name, server in self.plex_instances.items():
                try:
                    if item_type == "movie":
                        item_dict = server.get_media(single_movie=True)
                    else:
                        item_dict = server.get_media(single_series=True)
                    if item_dict:
                        if item_type == "movie":
                            plex_media_dict[name] = {"all_movies": item_dict}
                        else:
                            plex_media_dict[name] = {"all_shows": item_dict}
                except Exception as e:
                    self.logger.error(
                        f"Error retrieving media for Plex instance '{name}': {e}"
                    )
                    plex_media_dict[name] = {}

            for server_name, item_dict in plex_media_dict.items():
                found_item = False
                if item_type == "movie":
                    updated_movie_dict = self.convert_plex_dict_titles_to_paths(
                        plex_movie_dict=item_dict["all_movies"],
                        plex_show_dict=None,
                    )

                    filtered_movies = {"movie": {}, "collections": {}}

                    self.logger.debug(pformat(updated_movie_dict))
                    if not isinstance(updated_movie_dict, dict):
                        self.logger.error(
                            f"Expected a dictionary, but got {type(updated_movie_dict)}"
                        )
                        continue

                    for library_name, movies in updated_movie_dict.items():
                        for movie_title, movie_obj in movies.items():
                            if item_title == movie_title:
                                found_item = True
                                filtered_movies["movie"].setdefault(library_name, {})[
                                    movie_title
                                ] = movie_obj

                    if found_item:
                        item_dict["all_movies"] = filtered_movies
                        self.logger.debug("Filtered media dict:")
                        self.logger.debug(pformat(plex_media_dict))
                        self.logger.info(
                            f"Uploading posters for Plex instance: {server_name}"
                        )
                        self.upload_poster(
                            webhook_cached_files,
                            plex_movie_dict=item_dict["all_movies"],
                            plex_show_dict=None,
                        )
                        break
                    else:
                        self.search_recently_added_for_items(
                            "movie",
                            item_title,
                            webhook_cached_files,
                        )

                else:
                    updated_show_dict = self.convert_plex_dict_titles_to_paths(
                        plex_movie_dict=None,
                        plex_show_dict=item_dict["all_shows"],
                    )
                    filtered_shows = {"show": {}, "collections": {}}

                    if not isinstance(updated_show_dict, dict):
                        self.logger.error(
                            f"Expected a dictionary, but got {type(updated_show_dict)}"
                        )
                        continue

                    for library_name, shows in updated_show_dict.items():
                        for show_title, show_obj in shows.items():
                            if item_title == show_title:
                                found_item = True
                                filtered_shows["show"].setdefault(library_name, {})[
                                    show_title
                                ] = show_obj

                    if found_item:
                        item_dict["all_shows"] = filtered_shows
                        self.logger.debug("Filtered media dict:")
                        self.logger.debug(pformat(plex_media_dict))
                        self.logger.info(
                            f"Uploading posters for Plex instance: {server_name}"
                        )
                        self.upload_poster(
                            webhook_cached_files,
                            plex_movie_dict=None,
                            plex_show_dict=item_dict["all_shows"],
                        )
                        break
                    else:
                        self.search_recently_added_for_items(
                            "show",
                            item_title,
                            webhook_cached_files,
                        )
