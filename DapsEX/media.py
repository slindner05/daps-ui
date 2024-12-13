import re
import time
from logging import Logger
from pathlib import Path

from arrapi import RadarrAPI, SonarrAPI
from arrapi.apis.sonarr import Series
from arrapi.exceptions import ConnectionFailure
from arrapi.exceptions import Unauthorized as ArrApiUnauthorized
from arrapi.objs.reload import Movie
from plexapi.collection import LibrarySection
from plexapi.exceptions import BadRequest
from plexapi.exceptions import Unauthorized as PlexApiUnauthorized
from plexapi.exceptions import UnknownType
from plexapi.server import PlexServer


class Media:
    def get_series_with_seasons(self, all_series_objects: list[Series]):
        titles_with_seasons = []
        for media_object in all_series_objects:
            dict_with_seasons = {
                "title": "",
                "seasons": [],
                "status": "",
                "has_episodes": False,
            }
            path = Path(media_object.path)  # type: ignore
            title = path.name
            series_status = media_object.status
            season_object = media_object.seasons
            dict_with_seasons["title"] = title
            dict_with_seasons["status"] = series_status

            for season in season_object:  # type: ignore
                season_dict = {
                    "season": "",
                    "has_episodes": True,
                }
                season_number = season.seasonNumber
                episode_count = season.episodeFileCount
                has_episodes = episode_count > 0
                formatted_season = f"season{season_number:02}"

                season_dict["season"] = formatted_season
                season_dict["has_episodes"] = has_episodes
                dict_with_seasons["seasons"].append(season_dict)

            if any(
                season.get("has_episodes", False)
                for season in dict_with_seasons["seasons"]
            ):
                dict_with_seasons["has_episodes"] = True

            titles_with_seasons.append(dict_with_seasons)
        return titles_with_seasons

    def get_movies_with_years(
        self, all_movie_objects: list[Movie]
    ) -> list[dict[str, str | list[str]]]:
        titles_with_years = []
        release_years = re.compile(r"^\d{4}")

        def extract_year(date_string):
            match = release_years.match(str(date_string))
            if match:
                return match.group(0)
            return None

        for media_object in all_movie_objects:
            dict_with_years = {"title": "", "years": [], "status": "", "has_file": None}

            path = Path(media_object.path)  # type: ignore
            title = path.name
            title_year = str(media_object.year)
            status = media_object.status
            has_file = media_object.hasFile
            years = [
                extract_year(media_object.physicalRelease),
                extract_year(media_object.digitalRelease),
                extract_year(media_object.inCinemas),
            ]
            dict_with_years["title"] = title
            dict_with_years["status"] = status
            dict_with_years["has_file"] = has_file

            for year in years:
                if year and year not in dict_with_years["years"] and year != title_year:
                    dict_with_years["years"].append(year)

            titles_with_years.append(dict_with_years)
        return titles_with_years


class Radarr(Media):
    def __init__(self, base_url: str, api: str, logger: Logger):
        super().__init__()
        self.logger = logger
        try:
            self.radarr = RadarrAPI(base_url, api)
            self.all_movie_objects = self.get_all_movies()
            self.movies = self.get_movies_with_years(self.all_movie_objects)
        except ArrApiUnauthorized as e:
            self.logger.error(
                "Error: Unauthorized access to Radarr. Please check your API key."
            )
            raise e
        except ConnectionFailure as e:
            self.logger.error(
                "Error: Connection to Radarr failed. Please check your base URL or network connection."
            )
            raise e

    def get_all_movies(self) -> list[Movie]:
        return self.radarr.all_movies()

    def get_movie(self, id: int):
        movie_list = []
        movie = self.radarr.get_movie(id)
        movie_list.append(movie)
        return self.get_movies_with_years(movie_list)


class Sonarr(Media):
    def __init__(self, base_url: str, api: str, logger: Logger):
        super().__init__()
        self.logger = logger
        try:
            self.sonarr = SonarrAPI(base_url, api)
            self.all_series_objects = self.get_all_series()
            self.series = self.get_series_with_seasons(self.all_series_objects)
        except ArrApiUnauthorized as e:
            self.logger.error(
                "Error: Unauthorized access to Sonarr. Please check your API key."
            )
            raise e
        except ConnectionFailure as e:
            self.logger.error(
                "Error: Connection to Sonarr failed. Please check your base URL or network connection."
            )
            raise e

    def get_all_series(self) -> list[Series]:
        return self.sonarr.all_series()

    def get_show(self, id: int):
        show_list = []
        show = self.sonarr.get_series(id)
        show_list.append(show)
        return self.get_series_with_seasons(show_list)


class Server:
    def __init__(
        self, plex_url: str, plex_token: str, library_names: list[str], logger: Logger
    ):
        self.logger = logger
        try:
            self.plex = PlexServer(plex_url, plex_token)
            self.library_names = library_names
            self.movie_collections, self.series_collections = self.get_collections()
        except PlexApiUnauthorized as e:
            self.logger.error(
                "Error: Unauthorized access to Plex. Please check your API key."
            )
            raise e
        except BadRequest as e:
            self.logger.error("Error: Bad request from Plex. Please check your config.")
            raise e

    def get_collections(self) -> tuple[list[str], list[str]]:
        movie_collections_list = []
        show_collections_list = []
        unique_collections = set()

        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
            except UnknownType as e:
                self.logger.error(f"Library '{library_name}' is invalid: {e}")
                continue

            if library.type == "movie":
                self._movie_collection(
                    library, unique_collections, movie_collections_list
                )
            if library.type == "show":
                self._show_collection(
                    library, unique_collections, show_collections_list
                )
        return movie_collections_list, show_collections_list

    def _movie_collection(
        self,
        library: LibrarySection,
        unique_collections: set,
        movie_collections_list: list[str],
    ) -> None:
        collections = library.collections()
        for collection in collections:
            if collection.title not in unique_collections:
                unique_collections.add(collection.title)
                movie_collections_list.append(collection.title)

    def _show_collection(
        self,
        library: LibrarySection,
        unique_collections: set,
        show_collections_list: list[str],
    ) -> None:
        collections = library.collections()
        for collection in collections:
            if collection.title not in unique_collections:
                unique_collections.add(collection.title)
                show_collections_list.append(collection.title)

    def get_media(self) -> tuple[dict[str, dict], dict[str, dict]]:
        movie_dict = {"movie": {}, "collections": {}}
        show_dict = {"show": {}, "collections": {}}

        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
            except UnknownType as e:
                self.logger.error(f"Library '{library_name}' is invalid: {e}")
                continue

            if library.type == "movie":
                self._process_library(library, movie_dict)
            if library.type == "show":
                self._process_library(library, show_dict)
        return movie_dict, show_dict

    def _process_library(
        self,
        library: LibrarySection,
        item_dict: dict[str, dict],
    ) -> None:
        all_items = library.all()
        all_collections = library.collections()
        for item in all_items:
            title_key = item.title
            year = item.year or ""
            title_name = f"{title_key} ({year})".strip()
            if title_name not in item_dict[library.type]:
                item_dict[library.type][title_name] = []
            item_dict[library.type][title_name].append(item)
        for collection in all_collections:
            collection_key = collection.title
            if collection_key not in item_dict["collections"]:
                item_dict["collections"][collection_key] = []
            item_dict["collections"][collection_key].append(collection)

    def get_single_item(self, media_type: str, title: str, year: int, logger):
        if media_type == "movie":
            item_dict = {"movie": {}}
        else:
            item_dict = {"show": {}}

        libraries_to_search = []
        max_retries = 10
        retry_delay = 30
        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
                if library.type == media_type:
                    libraries_to_search.append(library)
            except UnknownType as e:
                self.logger.error(f"Library '{library_name}' is invalid: {e}")
                continue

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    f"Attempt {attempt}/{max_retries}: Searching for '{title} {year}' across {len(libraries_to_search)} libraries"
                )
                for library in libraries_to_search:
                    logger.debug(
                        f"Library to search: '{library.title}', Type: '{library.type}'"
                    )
                    logger.debug(
                        f"Searching with parameters: title='{title}', year={year}"
                    )
                    results = library.search(title=title, year=year)
                    if results:
                        logger.debug(f"Found item in library '{library.title}'")
                    for item in results:
                        title_key = item.title
                        year_key = item.year or ""
                        title_name = f"{title_key} ({year_key})".strip()
                        if title_name not in item_dict[library.type]:
                            item_dict[library.type][title_name] = []
                        item_dict[library.type][title_name].append(item)

                if item_dict:
                    return item_dict

                logger.warning(
                    f"No results found for '{title} {year}' on attempt {attempt}/{max_retries}"
                )

            except Exception as e:
                logger.error(
                    f"Error during search for '{title} {year}' on attempt {attempt}/{max_retries}: {e}"
                )

            if attempt < max_retries:
                time.sleep(retry_delay)

        logger.error(
            f"Failed to retrieve item '{title} {year}' from any library after {max_retries} attempts"
        )
        return None
