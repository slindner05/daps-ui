# TODO: ADD A WAY TO CLEAN ASSET DIRECTORY WHEN ASSET FOLDERS CHANGES

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
from DapsEX.media import Media, Radarr, Server, Sonarr
from DapsEX.settings import Settings
from Payloads.poster_renamerr_payload import Payload
from progress import ProgressState


class PosterRenamerr:
    def __init__(
        self,
        target_path: str,
        source_directories: list,
        asset_folders: bool,
        replace_border: bool,
        log_level=logging.INFO,
    ):
        try:
            log_dir = Path(Settings.LOG_DIR.value) / Settings.POSTER_RENAMERR.value
            self.target_path = Path(target_path)
            self.source_directories = source_directories
            self.asset_folders = asset_folders
            self.replace_border = replace_border
            self.db = Database()
            self.test = BorderReplacerr()
            self.logger = logging.getLogger("PosterRenamerr")
            init_logger(self.logger, log_dir, "poster_renamerr", log_level=log_level)
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
                if poster.suffix.lower() in self.image_exts:
                    if source_dir not in source_files:
                        source_files[source_dir] = []
                    if poster not in unique_files:
                        unique_files.add(poster.name)
                        source_files[source_dir].append(poster)
                    else:
                        self.logger.debug(f"⏩ Skipping duplicate file: {poster}")
                else:
                    self.logger.debug(f"⏩ Skipping non-image file: {poster}")
        return source_files

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
        matched_movies_with_year = {}

        flattened_col_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        movies_list = media_dict.get("movies", [])
        shows_list = media_dict.get("shows", [])

        total_files = sum(len(files) for files in source_files.values())
        processed_files = 0

        for directory, files in source_files.items():
            for file in tqdm(files, desc=f"Matching files in {directory}"):
                name_without_extension = file.stem
                sanitized_name_without_extension = self._remove_chars(
                    name_without_extension
                )
                sanitized_name_without_year = utils.strip_year(
                    sanitized_name_without_extension
                )
                year_match = re.search(r"(\b\d{4}\b)", file.stem)
                season_match = re.search(
                    r"\b- (season|specials)\b", file.stem, re.IGNORECASE
                )
                poster_file_year = year_match.group(1) if year_match else None
                matched = False

                for matched_list in matched_files.values():
                    for matched_file in matched_list:
                        stripped_file_name = self._remove_chars(matched_file.stem)
                        if sanitized_name_without_extension == stripped_file_name:
                            self.logger.debug(f"Exact match found: {file}, skipping")
                            matched = True
                        if (
                            not matched
                            and sanitized_name_without_year in matched_movies_with_year
                            and poster_file_year is not None
                            and poster_file_year
                            in matched_movies_with_year[sanitized_name_without_year]
                        ):
                            self.logger.debug(
                                f"Year-based match found: {file}, skipping"
                            )
                            matched = True
                            break
                    if matched:
                        break
                if matched:
                    continue

                if not matched and not poster_file_year and not season_match:
                    for collection_name in flattened_col_list:
                        sanitized_collection_name = self._remove_chars(
                            collection_name
                        ).removesuffix(" collection")
                        sanitized_file_name_without_collection = (
                            sanitized_name_without_extension.removesuffix(" collection")
                        )
                        if (
                            sanitized_file_name_without_collection
                            == sanitized_collection_name
                        ):
                            matched_files["collections"].append(file)
                            matched = True
                            break
                    if matched:
                        continue

                if not matched and poster_file_year and not season_match:
                    for movie_data in movies_list:
                        movie_title = movie_data.get("title", "")
                        movie_years = movie_data.get("years", [])
                        movie_status = movie_data.get("status", "")
                        sanitized_movie_title = utils.strip_id(
                            self._remove_chars(movie_title)
                        )
                        sanitized_movie_title_without_year = utils.strip_year(
                            sanitized_movie_title
                        )

                        if sanitized_name_without_extension == sanitized_movie_title:
                            matched = True

                        if not matched and movie_years:
                            for year in movie_years:
                                sanitized_movie_title_alternate_year = (
                                    f"{sanitized_movie_title_without_year} ({year})"
                                )
                                if (
                                    sanitized_name_without_extension
                                    == sanitized_movie_title_alternate_year
                                ):
                                    matched = True
                                    break
                        if matched:
                            matched_files["movies"][file] = movie_status
                            self.logger.debug(f"Added {file} to matched_files dict")
                            if (
                                sanitized_movie_title_without_year
                                not in matched_movies_with_year
                            ):
                                matched_movies_with_year[
                                    sanitized_movie_title_without_year
                                ] = set()
                            matched_movies_with_year[
                                sanitized_movie_title_without_year
                            ].update(movie_years)
                            break
                    if matched:
                        continue

                if not matched and poster_file_year:
                    for show_data in shows_list:
                        show_name = show_data.get("title", "")
                        show_status = show_data.get("status", "")
                        show_seasons = show_data.get("seasons", [])
                        sanitized_show_name = utils.strip_id(
                            self._remove_chars(show_name)
                        )
                        season_num_match = re.search(
                            r"- Season (\d+)", file.stem, re.IGNORECASE
                        )
                        if season_num_match:
                            season_num = int(season_num_match.group(1))
                            if self._match_show_season(
                                sanitized_name_without_extension, sanitized_show_name
                            ):
                                for season in show_seasons:
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
                                            matched_files["shows"][
                                                file
                                            ] = season_has_episodes
                                            matched = True
                                            break
                                if matched:
                                    break

                        if self._match_show_special(
                            sanitized_name_without_extension, sanitized_show_name
                        ):
                            for season in show_seasons:
                                if "season00" in season.get("season", ""):
                                    season_has_episodes = season.get(
                                        "has_episodes", None
                                    )
                                    matched_files["shows"][file] = season_has_episodes
                                    matched = True
                                    break
                            if matched:
                                break

                        if sanitized_name_without_extension == sanitized_show_name:
                            matched_files["shows"][file] = show_status
                            matched = True
                            break
                    if matched:
                        continue

                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)

        self.logger.debug("Matched files summary:")
        self.logger.debug(pformat(matched_files))
        return matched_files

    @staticmethod
    def _match_show_season(file_name: str, show_name: str) -> bool:
        season_pattern = re.compile(
            rf"{re.escape(show_name)} - Season \d+", re.IGNORECASE
        )
        if season_pattern.match(file_name):
            return True

        return False

    @staticmethod
    def _match_show_special(file_name: str, show_name: str) -> bool:
        specials_pattern = re.compile(
            rf"{re.escape(show_name)} - Specials", re.IGNORECASE
        )
        if specials_pattern.match(file_name):
            return True

        return False

    @staticmethod
    def _remove_emojis(name: str) -> str:
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f700-\U0001f77f"  # alchemical symbols
            "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
            "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
            "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
            "\U0001fa00-\U0001fa6f"  # Chess Symbols, etc.
            "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
            "\U00002700-\U000027bf"  # Dingbats
            "\U0001f1e0-\U0001f1ff"  # Flags
            "]+",
            flags=re.UNICODE,
        )
        return emoji_pattern.sub(r"", name)

    def create_asset_directories(
        self, collections_dict: dict[str, list[str]], media_dict: dict[str, list]
    ) -> dict[str, list[str]]:
        asset_folder_names = {"collections": [], "movies": [], "shows": []}
        self.target_path.mkdir(parents=True, exist_ok=True)
        for key, items in collections_dict.items():
            for name in items:
                sanitized_name = sanitize_filename(name)
                sub_dir = self.target_path / sanitized_name
                if not sub_dir.exists():
                    try:
                        sub_dir.mkdir(exist_ok=True)
                        self.logger.info(f"Directory created: {sub_dir}")
                    except Exception as e:
                        self.logger.error(
                            f"Failed to create directory for {sanitized_name}: {e}"
                        )
                asset_folder_names["collections"].append(sub_dir.name)

        for key, items in media_dict.items():
            for media_data in items:
                name = media_data.get("title", "")
                sanitized_name = sanitize_filename(name)
                sub_dir = self.target_path / sanitized_name
                if not sub_dir.exists():
                    try:
                        sub_dir.mkdir(exist_ok=True)
                        self.logger.info(f"Directory created: {sub_dir}")
                    except Exception as e:
                        self.logger.error(
                            f"Failed to create directory for {sanitized_name}: {e}"
                        )
                if key == "movies":
                    asset_folder_names["movies"].append(sanitized_name)
                elif key == "shows":
                    asset_folder_names["shows"].append(sanitized_name)

        return asset_folder_names

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

    def copy_rename_files_asset_folders(
        self,
        matched_files: dict[str, dict],
        asset_folder_names: dict[str, list[str]],
    ) -> None:
        for key, items in matched_files.items():
            if key == "movies":
                for file_path, status in items.items():
                    result = self._handle_movie_asset_folders(
                        asset_folder_names, file_path
                    )
                    if not result:
                        continue

                    target_dir, file_name_format = result
                    self._copy_file(
                        file_path,
                        key,
                        target_dir,
                        file_name_format,
                        self.replace_border,
                        status=status,
                    )

            elif key == "collections":
                for item in items:
                    result = self._handle_collection_asset_folders(
                        asset_folder_names, item
                    )
                    if not result:
                        continue
                    target_dir, file_name_format = result
                    self._copy_file(
                        item, key, target_dir, file_name_format, self.replace_border
                    )

            elif key == "shows":
                for file_path, data in items.items():
                    result = self._handle_series_asset_folders(
                        asset_folder_names, file_path
                    )
                    if not result:
                        continue

                    target_dir, file_name_format = result
                    if isinstance(data, bool):
                        has_episodes = data
                        status = None
                    else:
                        has_episodes = None
                        status = data

                    self._copy_file(
                        file_path,
                        key,
                        target_dir,
                        file_name_format,
                        self.replace_border,
                        status=status,
                        has_episodes=has_episodes,
                    )

    def _handle_movie_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        for name in asset_folder_names["movies"]:
            asset_folder_name_without_year = self._remove_chars(
                utils.strip_year(utils.strip_id(name))
            )
            if (
                file_path.exists()
                and file_path.is_file()
                and self._remove_chars(utils.strip_year(utils.strip_id(file_path.stem)))
                == asset_folder_name_without_year
            ):
                self.log_matched_file("movie", name, str(file_path))
                movie_file_name_format = f"Poster{file_path.suffix}"
                target_dir = self.target_path / name
                return target_dir, movie_file_name_format
        return None

    def _handle_collection_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        for name in asset_folder_names["collections"]:
            stripped_file_name = self._remove_chars(file_path.stem).removesuffix(
                " collection"
            )
            stripped_asset_folder_name = self._remove_chars(name).removesuffix(
                " collection"
            )
            if (
                file_path.exists()
                and file_path.is_file()
                and stripped_file_name == stripped_asset_folder_name
            ):
                self.log_matched_file("collection", name, str(file_path))
                collection_file_name_format = f"Poster{file_path.suffix}"
                target_dir = self.target_path / name
                return target_dir, collection_file_name_format
        return None

    def _handle_series_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        match_season = re.match(r"(.+?) - Season (\d+)", file_path.stem)
        match_specials = re.match(r"(.+?) - Specials", file_path.stem)

        def clean_show_name(show: str) -> str:
            return utils.strip_id(self._remove_chars(show))

        if match_season:
            show_name_season = match_season.group(1)
            season_num = int(match_season.group(2))
            formatted_season_num = f"Season{season_num:02}"
            for name in asset_folder_names["shows"]:
                stripped_name = clean_show_name(name)
                if (
                    file_path.exists()
                    and file_path.is_file()
                    and self._remove_chars(show_name_season) == stripped_name
                ):
                    self.log_matched_file(
                        "season", name, str(file_path), f"{formatted_season_num}"
                    )
                    target_dir = self.target_path / name
                    show_file_name_season_format = (
                        f"{formatted_season_num}{file_path.suffix}"
                    )
                    return target_dir, show_file_name_season_format
            return None

        elif match_specials:
            show_name_specials = match_specials.group(1)
            for name in asset_folder_names["shows"]:
                stripped_name = clean_show_name(name)
                if (
                    file_path.exists()
                    and file_path.is_file()
                    and self._remove_chars(show_name_specials) == stripped_name
                ):
                    self.log_matched_file("special", name, str(file_path), "Season00")
                    target_dir = self.target_path / name
                    show_file_name_special_format = f"Season00{file_path.suffix}"
                    return target_dir, show_file_name_special_format
            return None

        else:
            for name in asset_folder_names["shows"]:
                stripped_name = clean_show_name(name)
                if (
                    file_path.exists()
                    and file_path.is_file()
                    and self._remove_chars(file_path.stem) == stripped_name
                ):
                    self.log_matched_file("series", name, str(file_path))
                    target_dir = self.target_path / name
                    show_file_name_format = f"Poster{file_path.suffix}"
                    return target_dir, show_file_name_format
            return None

    def _copy_file(
        self,
        file_path: Path,
        media_type: str,
        target_dir: Path,
        new_file_name: str,
        replace_border: bool = False,
        status: str | None = None,
        has_episodes: bool | None = None,
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
            cached_has_episodes = cached_file.get("has_episodes", None)
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
            self.logger.debug(f"Cached status: {cached_status}")
            self.logger.debug(f"Current status: {status}")
            self.logger.debug(f"Cached has_episodes: {cached_has_episodes}")
            self.logger.debug(f"Current has_episodes: {has_episodes}")

            if cached_has_episodes and has_episodes:
                if cached_has_episodes != has_episodes:
                    self.db.update_has_episodes(
                        str(file_path), has_episodes, self.logger
                    )

            if cached_status and status:
                if cached_status != status:
                    self.db.update_status(str(file_path), status, self.logger)

            if (
                cached_original_hash == original_file_hash
                and cached_source == current_source
                and cached_border_state == replace_border
            ):
                self.logger.debug(f"⏩ Skipping unchanged file: {file_path}")
                return

        if replace_border:
            try:
                final_image = self.test.remove_border(file_path)
                temp_path = target_dir / f"temp_{new_file_name}"
                final_image.save(temp_path)
                self.logger.info(f"Replaced border on {file_path.name}")
                file_path = temp_path
                file_hash = self.hash_file(file_path)
            except Exception as e:
                self.logger.error(f"Error removing border for {file_path}: {e}")
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
                    file_hash,
                    original_file_hash,
                    current_source,
                    str(target_path),
                    border_replaced=replace_border,
                )
                self.logger.debug(f"Replaced cached file: {cached_file} -> {file_path}")
            else:
                self.db.add_file(
                    str(target_path),
                    file_name_without_extension,
                    status,
                    has_episodes,
                    media_type,
                    file_hash,
                    original_file_hash,
                    current_source,
                    border_replaced=replace_border,
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
    ) -> None:
        show_dict_list = media_dict.get("shows", [])
        movies_dict_list = media_dict.get("movies", [])
        collections_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        for key, items in matched_files.items():
            if key == "movies":
                for file_path, status in items.items():
                    movie_result = self._handle_movie(file_path, movies_dict_list)
                    if not movie_result:
                        continue
                    file_name_format = sanitize_filename(movie_result)
                    self._copy_file(
                        file_path,
                        key,
                        self.target_path,
                        file_name_format,
                        self.replace_border,
                        status=status,
                        has_episodes=None,
                    )

            if key == "collections":
                for item in items:
                    collection_result = self._handle_collections(item, collections_list)
                    if not collection_result:
                        continue
                    file_name_format = sanitize_filename(collection_result)
                    self._copy_file(
                        item,
                        key,
                        self.target_path,
                        file_name_format,
                        self.replace_border,
                        status=None,
                        has_episodes=None,
                    )

            if key == "shows":
                for file_path, data in items.items():
                    show_result = self._handle_series(file_path, show_dict_list)
                    if not show_result:
                        continue
                    file_name_format = sanitize_filename(show_result)
                    if isinstance(data, bool):
                        has_episodes = data
                        status = None
                    else:
                        has_episodes = None
                        status = data
                    self._copy_file(
                        file_path,
                        key,
                        self.target_path,
                        file_name_format,
                        self.replace_border,
                        status=status,
                        has_episodes=has_episodes,
                    )

    def convert_plex_dict_titles_to_paths(self, plex_movie_dict, plex_show_dict):

        updated_movie_dict = {}
        updated_show_dict = {}

        for plex_title, show_list in plex_show_dict.get("show", {}).items():
            show = show_list[0]
            try:
                first_season = show.seasons()[0]
                first_episode = first_season.episodes()[0]
                first_media = first_episode.media[0]
                first_part = first_media.parts[0]
                item_path = Path(first_part.file)
                new_title = item_path.parent.parent.name
                updated_show_dict[new_title] = show_list
                # self.logger.debug(
                #     f"Updated Plex show title: '{plex_title}' -> {new_title}"
                # )
            except Exception as e:
                self.logger.warning(
                    f"Could not determine path for show: {show.title}. Error: {e}"
                )

        for plex_title, movie_list in plex_movie_dict.get("movie", {}).items():
            movie = movie_list[0]
            try:
                media_parts = next(
                    (media.parts for media in movie.media if media.parts), None
                )
                if media_parts:
                    file_part = next(
                        (part.file for part in media_parts if part.file), None
                    )
                    if file_part:
                        item_path = Path(file_part)
                        new_title = item_path.parent.name
                        updated_movie_dict[new_title] = movie_list
                        # self.logger.debug(
                        #     f"Updated Plex movie title: '{plex_title}' -> {new_title}"
                        # )
                    else:
                        raise ValueError(f"No valid file part found for {movie.title}")
                else:
                    raise ValueError(f"No valid media parts found for {movie.title}")
            except Exception as e:
                self.logger.warning(
                    f"Could not determine path for movie: {movie.title}. Error: {e}"
                )
        return updated_movie_dict, updated_show_dict

    def upload_poster(
        self, cached_files, plex_movie_dict, plex_show_dict, asset_folders: bool
    ) -> None:

        def filter_cached_files_by_type(cached_files, media_type):
            return {
                file_path: file_info
                for file_path, file_info in cached_files.items()
                if file_info.get("media_type") == media_type
            }

        def find_match(
            file_name,
            plex_items,
        ):
            for title, item_list in plex_items.items():
                item_name = self._remove_chars(title)
                # self.logger.debug(
                #     f"Comparing cached file '{file_name}' with Plex item '{item_name}'"
                # )
                if file_name == item_name:
                    return item_list
            self.logger.warning(f"No match found for file: {file_name}")
            return None

        def add_poster_to_plex(
            plex_media_objects: list, file_path: str, show_title: str | None = None
        ):
            try:
                for item in plex_media_objects:
                    item.uploadPoster(filepath=file_path)
                self.db.update_uploaded_to_plex(file_path, self.logger)
                if show_title:
                    self.logger.info(
                        f"Successfully uploaded poster for '{show_title}', item {plex_media_objects[0].title}"
                    )
                else:
                    self.logger.info(
                        f"Successfully uploaded poster for item {plex_media_objects[0].title}"
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

        movies_only = filter_cached_files_by_type(cached_files, "movies")
        collections_only = filter_cached_files_by_type(cached_files, "collections")
        shows_only = filter_cached_files_by_type(cached_files, "shows")

        combined_collection_dict = {
            **plex_movie_dict["collections"],
            **plex_show_dict["collections"],
        }
        processed_files = set()

        for file_path, file_info in movies_only.items():
            if asset_folders:
                asset_file_path = Path(file_path)
                file_name = self._remove_chars(asset_file_path.parent.name)
            else:
                file_name = self._remove_chars(file_info["file_name"])
            self.logger.debug(
                f"Processing cached movie file: {file_path}, Normalized title: {file_name}"
            )
            movie_list = find_match(file_name, plex_movie_dict["movie"])
            if movie_list:
                self.logger.debug(
                    f"Match found for file '{file_path}' -> Plex movie '{movie_list[0].title}'"
                )
                if file_path not in processed_files:
                    processed_files.add(file_path)
                    add_poster_to_plex(movie_list, file_path)

        for file_path, file_info in shows_only.items():
            if asset_folders:
                season_match = re.match(r"^Season(\d{2})", file_info["file_name"])
            else:
                season_match = re.match(
                    r"^(.*\s\(\d{4}\)\s.*)_Season(\d{2}).*$", file_info["file_name"]
                )
            if season_match:
                if asset_folders:
                    asset_file_path = Path(file_path)
                    file_name = self._remove_chars(asset_file_path.parent.name)
                    season_num = int(season_match.group(1))
                else:
                    file_name = self._remove_chars(f"{season_match.group(1)}")
                    season_num = int(season_match.group(2))
                self.logger.debug(
                    f"Processing cached show file: {file_path}, Normalized title: {file_name}"
                )
                show_list = find_match(
                    file_name,
                    plex_show_dict["show"],
                )
                if show_list:
                    matching_seasons = []
                    for show in show_list:
                        season = next(
                            (s for s in show.seasons() if s.index == season_num),
                            None,
                        )
                        if season:
                            matching_seasons.append((show.title, season))
                    if matching_seasons:
                        first_show_title, first_season = matching_seasons[0]
                        self.logger.debug(
                            f"Match found for Season {first_season} for Show {first_show_title}"
                        )
                        seasons_only = [season for _, season in matching_seasons]
                        if file_path not in processed_files:
                            processed_files.add(file_path)
                            add_poster_to_plex(
                                seasons_only, file_path, first_show_title
                            )
                    else:
                        for show in show_list:
                            self.logger.warning(
                                f"Season {season_num} not found for show '{show.title}'"
                            )
            else:
                if asset_folders:
                    asset_file_path = Path(file_path)
                    file_name = self._remove_chars(asset_file_path.parent.name)
                else:
                    file_name = self._remove_chars(file_info["file_name"])

                self.logger.debug(
                    f"Processing cached show file: {file_path}, Normalized title: {file_name}"
                )
                show_list = find_match(file_name, plex_show_dict["show"])
                if show_list:
                    self.logger.debug(
                        f"Match found for file '{file_path}' -> Plex show '{show_list[0].title}'"
                    )
                    if file_path not in processed_files:
                        processed_files.add(file_path)
                        add_poster_to_plex(show_list, file_path)

        for file_path, file_info in collections_only.items():
            if asset_folders:
                asset_file_path = Path(file_path)
                file_name = self._remove_chars(asset_file_path.parent.name)
            else:
                file_name = self._remove_chars(file_info["file_name"])
            self.logger.debug(
                f"Processing cached collection file: {file_path}, Normalized title: {file_name}"
            )
            collection_list = find_match(file_name, combined_collection_dict)
            if collection_list:
                self.logger.debug(
                    f"Match found for file '{file_path}' -> Plex collection '{collection_list[0].title}'"
                )
                if file_path not in processed_files:
                    processed_files.add(file_path)
                    add_poster_to_plex(collection_list, file_path)

    def _handle_movie(self, item: Path, movies_list_dict: list[dict]) -> str | None:
        movie_matched_without_year = self._remove_chars(
            utils.strip_year(utils.strip_id(item.stem))
        )
        for item_dict in movies_list_dict:
            movie_title = item_dict.get("title", "")
            movie_clean_without_year = self._remove_chars(
                utils.strip_year(utils.strip_id(movie_title))
            )
            if movie_matched_without_year == movie_clean_without_year:
                self.log_matched_file("movie", movie_title, str(item))
                movie_name = movie_title
                if item.exists() and item.is_file():
                    file_name_format = f"{movie_name}{item.suffix}"
                    return file_name_format
        return None

    def _handle_collections(
        self, item: Path, collections_list: list[str]
    ) -> str | None:
        collection_name = self._remove_chars(item.stem).removesuffix(" collection")
        for collection in collections_list:
            collection_clean = self._remove_chars(collection).removesuffix(
                " collection"
            )
            if collection_name == collection_clean:
                self.log_matched_file("collection", collection, str(item))
                collection_name = collection
                if item.exists() and item.is_file():
                    file_name_format = f"{collection_name}{item.suffix}"
                    return file_name_format
        return None

    def _handle_series(self, item: Path, show_list_dict: list[dict]) -> str | None:
        match_season = re.match(r"(.+?) - Season (\d+)", item.stem)
        match_specials = re.match(r"(.+?) - Specials", item.stem)

        def clean_show_name(show: str) -> str:
            return utils.strip_id(self._remove_chars(show))

        if match_season:
            show_name_season = self._remove_chars(match_season.group(1))
            season_num = int(match_season.group(2))
            formatted_season_num = f"Season{season_num:02}"
            for item_dict in show_list_dict:
                show_name = item_dict.get("title", "")
                show_clean = clean_show_name(show_name)
                if show_name_season == show_clean:
                    self.log_matched_file(
                        "season", show_name, str(item), formatted_season_num
                    )
                    show_name_season = show_name
                    if item.exists() and item.is_file():
                        file_name_format = (
                            f"{show_name_season}_{formatted_season_num}{item.suffix}"
                        )
                        return file_name_format
            return None
        elif match_specials:
            show_name_specials = self._remove_chars(match_specials.group(1))
            for item_dict in show_list_dict:
                show_name = item_dict.get("title", "")
                show_clean = clean_show_name(show_name)
                if show_name_specials == show_clean:
                    self.log_matched_file("special", show_name, str(item), "Season00")
                    show_name_specials = show_name
                    if item.exists() and item.is_file():
                        file_name_format = f"{show_name_specials}_Season00{item.suffix}"
                        return file_name_format
            return None
        else:
            show_name_normal = self._remove_chars(item.stem)
            for item_dict in show_list_dict:
                show_name = item_dict.get("title", "")
                show_clean = clean_show_name(show_name)
                if show_name_normal == show_clean:
                    self.log_matched_file("series", show_name, str(item))
                    show_name_normal = show_name
                    if item.exists() and item.is_file():
                        file_name_format = f"{show_name_normal}{item.suffix}"
                        return file_name_format
        return None

    def _remove_chars(self, file_name: str) -> str:
        file_name = re.sub(r"(?<=\w)-\s", " ", file_name)
        file_name = re.sub(r"(?<=\w)\s-\s", " ", file_name)
        file_name = re.sub(r"[\*\^;~\\`\[\]'\"\/,.!?:_…]", "", file_name)
        file_name = self._remove_emojis(file_name)
        return file_name.strip().replace("&", "and").replace("\u00a0", " ").lower()

    # TODO: ADD CHECK TO SEE IF SINGLE ITEM EXISTS ALREADY
    # TODO: ADD WAY TO 'QUEUE' MULTIPLE ITEMS
    def handle_single_item(
        self,
        asset_type: str,
        instances: dict,
        single_item: dict,
    ) -> dict[str, list] | None:

        media_dict = {"movies": [], "shows": []}
        instance_name = single_item.get("instance_name")
        item_id = single_item.get("item_id")
        if not instance_name:
            self.logger.error("Instance name is missing for movie item")
            return None
        if not item_id or not isinstance(item_id, int):
            self.logger.error(
                f"Invalid item ID: {item_id} for instance: {instance_name}"
            )
            return None
        arr_instance = instances.get(instance_name)
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
        payload: Payload,
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
        single_item: dict | None = None,
    ) -> None:
        from DapsEX import utils

        try:
            self._log_banner()
            media = Media()
            self.logger.debug("Creating Radarr Sonarr and Plex instances.")
            radarr_instances, sonarr_instances = utils.create_arr_instances(
                payload, Radarr, Sonarr, self.logger
            )
            plex_instances = utils.create_plex_instances(payload, Server, self.logger)
            self.logger.debug("Successfully created all instances")

            if single_item:
                self.logger.info("Run triggered for a single item via webhook")
                asset_type = single_item.get("type", "")
                combined_instances_dict = radarr_instances | sonarr_instances
                collections_dict = {"movies": [], "shows": []}

                media_dict = self.handle_single_item(
                    asset_type, combined_instances_dict, single_item
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
                all_movies, all_series = utils.get_combined_media_lists(
                    radarr_instances, sonarr_instances
                )
                all_movie_collections, all_series_collections = (
                    utils.get_combined_collections_lists(plex_instances)
                )
                media_dict, collections_dict = media.get_dicts(
                    all_movies,
                    all_series,
                    all_movie_collections,
                    all_series_collections,
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
                asset_folder_names = self.create_asset_directories(
                    collections_dict, media_dict
                )
                self.logger.debug("Copying and renaming files")
                self.copy_rename_files_asset_folders(matched_files, asset_folder_names)
            else:
                self.logger.debug(
                    "-------------------------------------------------------"
                )
                self.logger.debug(f"Asset Folders: {self.asset_folders}")
                self.logger.debug("Starting file copying and renaming")
                self.copy_rename_files(matched_files, media_dict, collections_dict)

            if payload.upload_to_plex:
                media_dict = {}
                cached_files = self.db.return_all_files()
                self.logger.debug(json.dumps(cached_files, indent=4))
                new_files = {
                    file_path: file_info
                    for file_path, file_info in cached_files.items()
                    if (
                        (
                            file_info.get("uploaded_to_plex") == 0
                            and file_info.get("has_episodes") == 1
                        )
                        or (
                            file_info.get("uploaded_to_plex") == 0
                            and file_info.get("status")
                            in {"released", "ended", "continuing"}
                        )
                        or (
                            file_info.get("uploaded_to_plex") == 0
                            and file_info.get("media_type") == "collections"
                        )
                    )
                }
                for file_path, file_info in new_files.items():
                    self.logger.info(
                        f"{file_path}: uploaded_to_plex={bool(file_info.get('uploaded_to_plex'))}"
                    )
                if new_files:
                    self.logger.debug(f"Total cached files: {len(cached_files)}")
                    self.logger.debug(f"New files to process: {len(new_files)}")
                    for name, server in plex_instances.items():
                        try:
                            plex_movie_dict, plex_show_dict = server.get_media()
                            media_dict[name] = {
                                "movies": plex_movie_dict,
                                "shows": plex_show_dict,
                            }
                        except Exception as e:
                            self.logger.error(
                                f"Error retrieving media for Plex instance '{name}': {e}"
                            )
                            media_dict[name] = {"movies": {}, "shows": {}}

                    for server_name, item_dict in media_dict.items():
                        updated_movie_dict, updated_show_dict = (
                            self.convert_plex_dict_titles_to_paths(
                                item_dict["movies"], item_dict["shows"]
                            )
                        )
                        item_dict["movies"]["movie"] = updated_movie_dict
                        item_dict["shows"]["show"] = updated_show_dict
                        self.logger.debug("Updated plex media dict:")
                        self.logger.debug(pformat(item_dict))

                        self.logger.info(
                            f"Uploading posters for Plex instance: {server_name}"
                        )
                        self.upload_poster(
                            new_files,
                            item_dict["movies"],
                            item_dict["shows"],
                            payload.asset_folders,
                        )
                else:
                    self.logger.info("No new files to upload to Plex")

            if job_id and cb:
                cb(job_id, 100, ProgressState.COMPLETED)
            self.clean_cache()
        except Exception as e:
            self.logger.critical("Unexpected error occured.", exc_info=True)
            raise
