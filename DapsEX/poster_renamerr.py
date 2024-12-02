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
    ) -> dict[str, list[Path]]:
        matched_files = {
            "collections": [],
            "movies": [],
            "shows": [],
        }

        flattened_col_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        append_str = " Collection"
        modified_col_list = [item + append_str for item in flattened_col_list]
        movies_list = media_dict.get("movies", [])

        total_files = sum(len(files) for files in source_files.values())
        processed_files = 0

        for directory, files in source_files.items():
            for file in tqdm(files, desc=f"Matching files in {directory}"):
                name_without_extension = file.stem
                sanitized_name_without_extension = self._remove_chars(
                    name_without_extension
                )
                matched = False

                for matched_list in matched_files.values():
                    if any(
                        sanitized_name_without_extension
                        == self._remove_chars(matched_file.stem)
                        for matched_file in matched_list
                    ):
                        matched = True
                        break

                if not matched:
                    for collection_name in modified_col_list:
                        sanitized_collection_name = self._remove_chars(collection_name)
                        if (
                            sanitized_name_without_extension
                            in sanitized_collection_name
                        ):
                            matched_files["collections"].append(file)
                            matched = True
                            break

                if not matched:
                    for movie_data in movies_list:
                        movie_title = movie_data.get("title")
                        movie_years = movie_data.get("years", [])
                        sanitized_movie_title = self._remove_chars(movie_title)
                        if sanitized_name_without_extension in sanitized_movie_title:
                            matched_files["movies"].append(file)
                            matched = True
                            break
                        if not matched and movie_years:
                            for year in movie_years:
                                sanitized_movie_title_without_year = self._strip_year(
                                    sanitized_movie_title
                                )
                                sanitized_movie_title_alternate_year = (
                                    f"{sanitized_movie_title_without_year} ({year})"
                                )
                                if (
                                    sanitized_name_without_extension
                                    in sanitized_movie_title_alternate_year
                                ):
                                    matched_files["movies"].append(file)
                                    matched = True
                                    break
                if not matched:
                    for show_name in media_dict["shows"]:
                        sanitized_show_name = self._strip_id(
                            self._remove_chars(show_name)
                        )
                        if (
                            sanitized_name_without_extension == sanitized_show_name
                            or self._match_show_season(
                                sanitized_name_without_extension,
                                sanitized_show_name,
                            )
                            or self._match_show_special(
                                sanitized_name_without_extension,
                                sanitized_show_name,
                            )
                        ):
                            matched_files["shows"].append(file)
                            matched = True
                            break
                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)

        if self.logger.isEnabledFor(logging.DEBUG):
            matched_files_str = {
                key: [str(path) for path in paths]
                for key, paths in matched_files.items()
            }
            self.logger.debug(
                "Matched files summary:\n%s", json.dumps(matched_files_str, indent=4)
            )
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
    def _strip_id(name: str) -> str:
        """
        Strip tvdb/imdb/tmdb ID from movie title.
        """
        return re.sub(r"\s*\{.*\}$", "", name)

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

    @staticmethod
    def _strip_year(name: str) -> str:
        return re.sub(r"\(\d{4}\)", "", name).strip()

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
            for name in items:
                if isinstance(name, dict):
                    sanitized_name = sanitize_filename(name["title"])
                else:
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
        matched_files: dict[str, list[Path]],
        asset_folder_names: dict[str, list[str]],
    ) -> None:
        for key, items in matched_files.items():
            if key == "movies":
                for item in items:
                    result = self._handle_movie_asset_folders(asset_folder_names, item)
                    if result:
                        target_dir, file_name_format = result
                        self._copy_file(
                            item, key, target_dir, file_name_format, self.replace_border
                        )

            elif key == "collections":
                for item in items:
                    result = self._handle_collection_asset_folders(
                        asset_folder_names, item
                    )
                    if result:
                        target_dir, file_name_format = result
                        self._copy_file(
                            item, key, target_dir, file_name_format, self.replace_border
                        )

            elif key == "shows":
                for item in items:
                    result = self._handle_series_asset_folders(asset_folder_names, item)
                    if result:
                        target_dir, file_name_format = result
                        self._copy_file(
                            item, key, target_dir, file_name_format, self.replace_border
                        )

    def _handle_movie_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        for name in asset_folder_names["movies"]:
            asset_folder_name_without_year = self._remove_chars(self._strip_year(name))
            if (
                file_path.exists()
                and file_path.is_file()
                and self._remove_chars(self._strip_year(file_path.stem))
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
            stripped_file_name = self._remove_chars(
                file_path.stem.removesuffix(" Collection")
            )
            if (
                file_path.exists()
                and file_path.is_file()
                and stripped_file_name == self._remove_chars(name)
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
            return self._strip_id(self._remove_chars(show))

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

    # TODO: ADD YEAR CHECK WHEN REPLACING FILES, CURRENTLY IF THE YEARS MISMATCH BETWEEN SOURCE DIRS PRIORITY FOR FILES BREAKS

    def _copy_file(
        self,
        file_path: Path,
        media_type: str,
        target_dir: Path,
        new_file_name: str,
        replace_border: bool = False,
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
        matched_files: dict[str, list[Path]],
        media_dict: dict[str, list],
        collections_dict: dict[str, list[str]],
    ) -> None:
        shows_list = media_dict.get("shows", [])
        movies_list_data = media_dict.get("movies", [])
        movies_list_titles = [movie["title"] for movie in movies_list_data]
        collections_list = [
            item for sublist in collections_dict.values() for item in sublist
        ]
        for key, items in matched_files.items():
            if key == "movies":
                for item in items:
                    result = self._handle_movie(item, movies_list_titles)
                    if result:
                        file_name_format = sanitize_filename(result)
                        self._copy_file(
                            item,
                            key,
                            self.target_path,
                            file_name_format,
                            self.replace_border,
                        )

            if key == "collections":
                for item in items:
                    result = self._handle_collections(item, collections_list)
                    if result:
                        file_name_format = sanitize_filename(result)
                        self._copy_file(
                            item,
                            key,
                            self.target_path,
                            file_name_format,
                            self.replace_border,
                        )

            if key == "shows":
                for item in items:
                    result = self._handle_series(item, shows_list)
                    if result:
                        file_name_format = sanitize_filename(result)
                        self._copy_file(
                            item,
                            key,
                            self.target_path,
                            file_name_format,
                            self.replace_border,
                        )

    def upload_poster(self, plex_movie_dict, plex_show_dict) -> None:
        cached_files = self.db.return_all_files()
        for file_path, file_info in cached_files.items():
            self.logger.info(
                f"{file_path}: uploaded_to_plex={file_info.get('uploaded_to_plex')}"
            )
        new_files = {
            file_path: file_info
            for file_path, file_info in cached_files.items()
            if file_info.get("uploaded_to_plex") in (None, 0)
        }
        self.logger.debug(f"Total cached files: {len(cached_files)}")
        self.logger.debug(f"New files to process: {len(new_files)}")

        def filter_cached_files_by_type(cached_files, media_type):
            return {
                file_path: file_info
                for file_path, file_info in cached_files.items()
                if file_info.get("media_type") == media_type
            }

        def add_show_paths(plex_show_dict):
            for show in plex_show_dict["show"]:
                try:
                    first_season = show.seasons()[0]
                    first_episode = first_season.episodes()[0]
                    first_media = first_episode.media[0]
                    first_part = first_media.parts[0]
                    item_path = Path(first_part.file)
                    show.path = item_path.parent.parent.name
                except Exception as e:
                    self.logger.warning(
                        f"Could not determine path for show: {show.title}. Error: {e}"
                    )
                    show.path = "Unknown"
            return plex_show_dict

        def find_match(
            file_name,
            plex_items,
            collection: bool = False,
            show: bool = False,
        ):
            for item in plex_items:
                if collection:
                    item_name = self._remove_chars(item.title)
                    self.logger.debug(
                        f"Comparing cached file '{file_name}' with Plex collection '{item_name}'"
                    )
                    if file_name == item_name:
                        return item
                elif show:
                    item_name = self._remove_chars(item.path)
                    self.logger.debug(
                        f"Comparing cached file '{file_name}' with Plex show '{item_name}'"
                    )
                    if file_name == item_name:
                        return item
                else:
                    for media in item.media:
                        for part in media.parts:
                            item_path = Path(part.file)
                            item_name = self._remove_chars(item_path.parent.name)
                            self.logger.debug(
                                f"Comparing cached file '{file_name}' with Plex movie '{item_name}'"
                            )
                            if file_name == item_name:
                                return item

            self.logger.warning(f"No match found for file: {file_name}")
            return None

        def add_poster_to_plex(plex_media_object, file_path):
            try:
                plex_media_object.uploadPoster(filepath=file_path)
                self.db.update_uploaded_to_plex(file_path, self.logger)
                self.logger.info(
                    f"Successfully uploaded poster for item {plex_media_object.title}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error uploading poster for item: {plex_media_object}: {e}"
                )

        movies_only = filter_cached_files_by_type(new_files, "movies")
        collections_only = filter_cached_files_by_type(new_files, "collections")
        shows_only = filter_cached_files_by_type(new_files, "shows")

        combined_collection_list = (
            plex_movie_dict["collections"] + plex_show_dict["collections"]
        )
        plex_show_dict = add_show_paths(plex_show_dict)

        for file_path, file_info in movies_only.items():
            file_name = self._remove_chars(file_info["file_name"])
            self.logger.info(
                f"Processing cached movie file: {file_path}, Normalized title: {file_name}"
            )
            movie = find_match(file_name, plex_movie_dict["movie"])
            if movie:
                self.logger.info(
                    f"Match found for file '{file_path}' -> Plex movie '{movie.title}'"
                )
                add_poster_to_plex(movie, file_path)

        for file_path, file_info in shows_only.items():
            season_match = re.match(
                r"^(.*\s\(\d{4}\)\s.*)_Season(\d{2}).*$", file_info["file_name"]
            )
            if season_match:
                file_name = self._remove_chars(f"{season_match.group(1)}")
                season_num = int(season_match.group(2))
                self.logger.info(
                    f"Processing cached show file: {file_path}, Normalized title: {file_name}"
                )
                show = find_match(file_name, plex_show_dict["show"], show=True)
                if show:
                    season = next(
                        (s for s in show.seasons() if s.index == season_num), None
                    )
                    if season:
                        self.logger.info(
                            f"Match found for Season {season.index}: {season.title}"
                        )
                        add_poster_to_plex(show, file_path)
                    else:
                        self.logger.warning(
                            f"Season {season_num} not found for show '{show.title}'"
                        )
            else:
                file_name = self._remove_chars(file_info["file_name"])
                self.logger.info(
                    f"Processing cached show file: {file_path}, Normalized title: {file_name}"
                )
                show = find_match(file_name, plex_show_dict["show"], show=True)
                if show:
                    self.logger.info(
                        f"Match found for file '{file_path}' -> Plex show '{show.title}'"
                    )
                    add_poster_to_plex(show, file_path)

        for file_path, file_info in collections_only.items():
            file_name = self._remove_chars(file_info["file_name"])
            self.logger.info(
                f"Processing cached collection file: {file_path}, Normalized title: {file_name}"
            )
            collection = find_match(
                file_name, combined_collection_list, collection=True
            )
            if collection:
                self.logger.info(
                    f"Match found for file '{file_path}' -> Plex collection '{collection.title}'"
                )
                add_poster_to_plex(collection, file_path)

    def _handle_movie(self, item: Path, movies_list: list[str]) -> str | None:
        movie_matched_without_year = self._remove_chars(self._strip_year(item.stem))
        for movie in movies_list:
            movie_clean_without_year = self._remove_chars(self._strip_year(movie))
            if movie_matched_without_year == movie_clean_without_year:
                self.log_matched_file("movie", movie, str(item))
                movie_name = movie
                if item.exists() and item.is_file():
                    file_name_format = f"{movie_name}{item.suffix}"
                    return file_name_format
        return None

    def _handle_collections(
        self, item: Path, collections_list: list[str]
    ) -> str | None:
        collection_name = self._remove_chars(item.stem.removesuffix(" Collection"))
        for collection in collections_list:
            collection_clean = self._remove_chars(collection)
            if collection_name == collection_clean:
                self.log_matched_file("collection", collection, str(item))
                collection_name = collection
                if item.exists() and item.is_file():
                    file_name_format = f"{collection_name}{item.suffix}"
                    return file_name_format
        return None

    def _handle_series(self, item: Path, shows_list: list[str]) -> str | None:
        match_season = re.match(r"(.+?) - Season (\d+)", item.stem)
        match_specials = re.match(r"(.+?) - Specials", item.stem)

        def clean_show_name(show: str) -> str:
            return self._strip_id(self._remove_chars(show))

        if match_season:
            show_name_season = self._remove_chars(match_season.group(1))
            season_num = int(match_season.group(2))
            formatted_season_num = f"Season{season_num:02}"
            for show in shows_list:
                show_clean = clean_show_name(show)
                if show_name_season == show_clean:
                    self.log_matched_file(
                        "season", show, str(item), formatted_season_num
                    )
                    show_name_season = show
                    if item.exists() and item.is_file():
                        file_name_format = (
                            f"{show_name_season}_{formatted_season_num}{item.suffix}"
                        )
                        return file_name_format
            return None
        elif match_specials:
            show_name_specials = self._remove_chars(match_specials.group(1))
            for show in shows_list:
                show_clean = clean_show_name(show)
                if show_name_specials == show_clean:
                    self.log_matched_file("special", show, str(item), "Season00")
                    show_name_specials = show
                    if item.exists() and item.is_file():
                        file_name_format = f"{show_name_specials}_Season00{item.suffix}"
                        return file_name_format
            return None
        else:
            show_name_normal = self._remove_chars(item.stem)
            for show in shows_list:
                show_clean = clean_show_name(show)
                if show_name_normal == show_clean:
                    self.log_matched_file("series", show, str(item))
                    show_name_normal = show
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

    # TODO: CREATE FUNCTION TO ADD has_episodes ATTRIBUTE TO PLEX MEDIA DICT FROM ARR MEDIA DICT
    # TODO: CREATE UPLOAD POSTER TO PLEX FUNCTION FOR ASSET FOLDERS
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
            # Re-assign the shows key to just have the titles of the shows
            media_dict["shows"] = [show["title"] for show in media_dict["shows"]]
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
                        self.logger.info(
                            f"Uploading posters for Plex instance: {server_name}"
                        )
                        self.upload_poster(item_dict["movies"], item_dict["shows"])

            if job_id and cb:
                cb(job_id, 100, ProgressState.COMPLETED)
            self.clean_cache()
        except Exception as e:
            self.logger.critical("Unexpected error occured.", exc_info=True)
            raise e
