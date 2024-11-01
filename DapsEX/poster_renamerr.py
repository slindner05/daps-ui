# TODO: add logging
from pathlib import Path
from Payloads.poster_renamerr_payload import Payload
from DapsEX.media import Server, Radarr, Sonarr, Media
from DapsEX.database_cache import Database
from DapsEX.border_replacerr import BorderReplacerr
import re
from tqdm import tqdm
import shutil
from pathvalidate import sanitize_filename
import hashlib
from progress import *
import pprint

class PosterRenamerr:
    def __init__(
        self,
        target_path: str,
        source_directories: list,
        asset_folders: bool,
        replace_border: bool,
    ):
        self.target_path = Path(target_path)
        self.source_directories = source_directories
        self.asset_folders = asset_folders
        self.replace_border = replace_border
        self.db = Database()
        self.border_replacerr = BorderReplacerr()

    image_exts = {".png", ".jpg", ".jpeg"}

    def hash_file(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def clean_cache(self) -> None:
        asset_files = [str(item) for item in Path(self.target_path).rglob("*")]
        cached_file_data = self.db.return_all_files()
        cached_file_paths = list(cached_file_data.keys())

        for item in cached_file_paths:
            if not item in asset_files:
                self.db.delete_cached_file(item)
                print(f"Removed deleted {item} from database")

    def get_source_files(self) -> dict[str, list[Path]]:
        source_directories = [Path(item) for item in self.source_directories]
        source_files = {}
        unique_files = set()
        for source_dir in source_directories:
            posters = list(source_dir.glob("*"))
            for poster in tqdm(posters, desc=f"Processing source files from {source_dir}"):
                if not poster.is_file():
                    continue
                if poster.suffix.lower() in self.image_exts:
                    if source_dir not in source_files:
                        source_files[source_dir] = []
                    if poster not in unique_files:
                        unique_files.add(poster.name)
                        source_files[source_dir].append(poster)
        return source_files

    def match_files_with_media(
        self,
        source_files: dict[str, list[Path]],
        media_dict: dict[str, list],
        collections_dict: dict[str, list[str]],
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
    ) -> dict[str, list[Path]]:
        # fuzzy_threshold = 85

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
                sanitized_name_without_extension = self._remove_chars(name_without_extension)
                # sanitized_name_without_extension_without_year = self._strip_year(sanitized_name_without_extension)
                matched = False
                # unmatched_files = []

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
                                    sanitized_movie_title_without_year = self._strip_year(sanitized_movie_title)
                                    sanitized_movie_title_alternate_year = f"{sanitized_movie_title_without_year} ({year})"
                                    if sanitized_name_without_extension in sanitized_movie_title_alternate_year:
                                        matched_files["movies"].append(file)
                                        matched = True
                                        break
                                # if not matched:
                                #     similarity_score = fuzz.partial_ratio(sanitized_name_without_extension, sanitized_movie_name)
                                #     if similarity_score >= 80:
                                #         print(f"{similarity_score} between {sanitized_name_without_extension} and {sanitized_movie_name}")
                                    # print(f"{similarity_score} for {sanitized_name_without_extension_without_year} and {sanitized_movie_name}")
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
                        # if not matched:
                        #     sanitized_show_name_without_year = self._strip_year(sanitized_show_name)
                        #     similarity_score = fuzz.partial_ratio(sanitized_name_without_extension_without_year, sanitized_show_name_without_year)
                        #     if similarity_score >= 80:
                        #         print(f"{similarity_score} between {sanitized_name_without_extension_without_year} and {sanitized_show_name_without_year}")

                processed_files += 1
                if job_id and cb:
                    progress = int((processed_files / total_files) * 70)
                    cb(job_id, progress + 10, ProgressState.IN_PROGRESS)

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
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols, etc.
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002700-\U000027BF"  # Dingbats
            "\U0001F1E0-\U0001F1FF"  # Flags
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
                    sub_dir.mkdir(exist_ok=True)
                    print(f"Directory created: {sub_dir}")
                asset_folder_names["collections"].append(sub_dir.name)

        for key, items in media_dict.items():
            for name in items:
                if isinstance(name, dict):
                    sanitized_name = sanitize_filename(name["title"])
                else:
                    sanitized_name = sanitize_filename(name)
                sub_dir = self.target_path / sanitized_name
                if not sub_dir.exists():
                    sub_dir.mkdir(exist_ok=True)
                    print(f"Directory created: {sub_dir}")
                if key == "movies":
                    asset_folder_names["movies"].append(sanitized_name)
                elif key == "shows":
                    asset_folder_names["shows"].append(sanitized_name)

        return asset_folder_names

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
                        self._copy_file(item, key, target_dir, file_name_format, self.replace_border)

            elif key == "collections":
                for item in items:
                    result = self._handle_collection_asset_folders(
                        asset_folder_names, item
                    )
                    if result:
                        target_dir, file_name_format = result
                        self._copy_file(item, key, target_dir, file_name_format, self.replace_border)

            elif key == "shows":
                for item in items:
                    result = self._handle_series_asset_folders(asset_folder_names, item)
                    if result:
                        target_dir, file_name_format = result
                        self._copy_file(item, key, target_dir, file_name_format, self.replace_border)

    def _handle_movie_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        for name in asset_folder_names["movies"]:
            asset_folder_name_without_year = self._remove_chars(self._strip_year(name))
            if file_path.exists() and file_path.is_file() and self._remove_chars(self._strip_year(file_path.stem)) == asset_folder_name_without_year:
                movie_file_name_format = f"Poster{file_path.suffix}"
                target_dir = self.target_path / name
                return target_dir, movie_file_name_format
        return None

    def _handle_collection_asset_folders(
        self, asset_folder_names: dict[str, list[str]], file_path: Path
    ) -> tuple[Path, str] | None:
        for name in asset_folder_names["collections"]:
            stripped_file_name = self._remove_chars(file_path.stem.removesuffix(" Collection"))
            if (
                file_path.exists()
                and file_path.is_file()
                and stripped_file_name == self._remove_chars(name)
            ):
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
                    target_dir = self.target_path / name
                    show_file_name_format = f"Poster{file_path.suffix}"
                    return target_dir, show_file_name_format
            return None

    # TODO: Add year check when replacing files, currently if the years mismatch between source dirs priority for files breaks

    def _copy_file(
        self, file_path: Path, media_type: str, target_dir: Path, new_file_name: str, replace_border: bool = False
    ) -> None:
        temp_path = None
        try:
            target_path = target_dir / new_file_name
            file_hash = self.hash_file(file_path)
            cached_file = self.db.get_cached_file(str(target_path))
            current_source = str(file_path)

            if replace_border:
                final_image = self.border_replacerr.remove_border(file_path)
                temp_path = target_dir / f"temp_{new_file_name}"
                final_image.save(temp_path)
                file_path = temp_path
                file_hash = self.hash_file(file_path)

            if target_path.exists() and cached_file:
                cached_hash = cached_file["file_hash"]
                cached_source = cached_file["source_path"]

                if file_hash != cached_hash or cached_source != current_source:
                    print(
                        f"Replacing file from {cached_source}: {current_source}\nCopied and renamed: {file_path.name} -> {target_path}"
                    )
                    shutil.copy2(file_path, target_path)
                    self.db.update_file(file_hash, current_source, str(target_path))
                else:
                    print(f"Skipping unchanged file: {file_path}")
                    return

            else:
                shutil.copy2(file_path, target_path)
                print(f"Copied and renamed: {file_path.name} -> {target_path}")
                self.db.add_file(
                    str(target_path), media_type, file_hash, current_source
                )

        except Exception as e:
            print(f"Error copying file {file_path}: {e}")

        finally:
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
                        self._copy_file(item, key, self.target_path, file_name_format, self.replace_border)

            if key == "collections":
                for item in items:
                    result = self._handle_collections(item, collections_list)
                    if result:
                        file_name_format = sanitize_filename(result)
                        self._copy_file(item, key, self.target_path, file_name_format, self.replace_border)

            if key == "shows":
                for item in items:
                    result = self._handle_series(item, shows_list)
                    if result:
                        file_name_format = sanitize_filename(result)
                        self._copy_file(item, key, self.target_path, file_name_format, self.replace_border)

    def _handle_movie(self, item: Path, movies_list: list[str]) -> str | None:
        movie_matched_without_year = self._remove_chars(self._strip_year(item.stem))
        for movie in movies_list:
            movie_clean_without_year = self._remove_chars(self._strip_year(movie))
            if movie_matched_without_year == movie_clean_without_year:
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
        return file_name.strip().replace("&", "and").replace("\u00A0", ' ').lower()

    def run(
        self,
        payload: Payload,
        cb: Callable[[str, int, ProgressState], None] | None = None,
        job_id: str | None = None,
    ) -> None:

        from DapsEX import utils

        try:
            media = Media()
            radarr_instances, sonarr_instances = utils.create_arr_instances(
                payload, Radarr, Sonarr
            )
            plex_instances = utils.create_plex_instances(payload, Server)
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
            # Re-assign the shows key to just have the titles of the shows
            media_dict["shows"] = [show["title"] for show in media_dict["shows"]]
            # pprint.pprint(media_dict["shows"], width=140)
            if job_id and cb:
                cb(job_id, 10, ProgressState.IN_PROGRESS)
            source_files = self.get_source_files()
            matched_files = self.match_files_with_media(
                source_files, media_dict, collections_dict, cb, job_id
            )
            if self.asset_folders:
                asset_folder_names = self.create_asset_directories(
                    collections_dict, media_dict
                )
                self.copy_rename_files_asset_folders(matched_files, asset_folder_names)
            else:
                self.copy_rename_files(matched_files, media_dict, collections_dict)

            if job_id and cb:
                cb(job_id, 100, ProgressState.COMPLETED)

            self.clean_cache()
        except Exception as e:
            print(f"Something went wrong: {e}", flush=True)
