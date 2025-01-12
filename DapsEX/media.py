import re
from logging import Logger
from pathlib import Path

from arrapi import RadarrAPI, SonarrAPI
from arrapi.apis.sonarr import Series
from arrapi.exceptions import ConnectionFailure
from arrapi.exceptions import Unauthorized as ArrApiUnauthorized
from arrapi.objs.reload import Movie
from plexapi.collection import LibrarySection
from plexapi.exceptions import BadRequest, UnknownType
from plexapi.exceptions import Unauthorized as PlexApiUnauthorized
from plexapi.server import PlexServer


class Media:
    def get_series_with_seasons(
        self, logger, all_series_objects: list[Series], instance_name: str
    ):
        titles_with_seasons = []
        for media_object in all_series_objects:
            dict_with_seasons = {
                "title": "",
                "id": None,
                "seasons": [],
                "status": "",
                "has_episodes": False,
                "alternate_titles": [],
                "instance": instance_name,
            }
            series_id = media_object.id
            path = Path(media_object.path)  # type: ignore
            title = path.name
            series_status = media_object.status
            season_object = media_object.seasons
            dict_with_seasons["title"] = title
            dict_with_seasons["status"] = series_status
            dict_with_seasons["id"] = series_id

            try:
                raw_api = media_object._raw
                series_data = raw_api.get_series_id(series_id)
                if series_data:
                    alternate_titles = self.extract_alternate_titles(
                        series_data.get("alternateTitles", [])
                    )
                    dict_with_seasons["alternate_titles"] = alternate_titles
            except Exception as e:
                logger.error(f"Error fetching series data for ID {series_id}: {e}")

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
        self, all_movie_objects: list[Movie], instance_name: str
    ) -> list[dict[str, str | list[str]]]:
        titles_with_years = []
        release_years = re.compile(r"^\d{4}")

        def extract_year(date_string):
            match = release_years.match(str(date_string))
            if match:
                return match.group(0)
            return None

        for media_object in all_movie_objects:
            dict_with_years = {
                "title": "",
                "id": None,
                "years": [],
                "status": "",
                "has_file": False,
                "instance": instance_name,
            }

            path = Path(media_object.path)  # type: ignore
            movie_id = media_object.id
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
            dict_with_years["id"] = movie_id

            for year in years:
                if year and year not in dict_with_years["years"] and year != title_year:
                    dict_with_years["years"].append(year)

            titles_with_years.append(dict_with_years)
        return titles_with_years

    def extract_alternate_titles(self, alternate_titles_list):
        return [
            title_entry["title"].strip()
            for title_entry in alternate_titles_list
            if title_entry.get("seasonNumber") == -1
            or title_entry.get("sceneSeasonNumber") == -1
            and title_entry.get("title", "").strip()
        ]


class Radarr(Media):
    def __init__(self, base_url: str, api: str, instance_name: str, logger: Logger):
        super().__init__()
        self.logger = logger
        try:
            self.radarr = RadarrAPI(base_url, api)
            self.instance_name = instance_name
            self.all_movie_objects = self.get_all_movies()
            self.movies = self.get_movies_with_years(
                self.all_movie_objects, self.instance_name
            )
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
        return self.get_movies_with_years(movie_list, self.instance_name)


class Sonarr(Media):
    def __init__(self, base_url: str, api: str, instance_name: str, logger: Logger):
        super().__init__()
        self.logger = logger
        try:
            self.sonarr = SonarrAPI(base_url, api)
            self.instance_name = instance_name
            self.all_series_objects = self.get_all_series()
            self.series = self.get_series_with_seasons(
                self.logger, self.all_series_objects, self.instance_name
            )
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
        return self.get_series_with_seasons(self.logger, show_list, self.instance_name)


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

    def get_media(
        self, single_movie: bool = False, single_series: bool = False
    ) -> tuple[dict[str, dict], dict[str, dict]] | dict[str, dict]:
        movie_dict = {"movie": {}, "collections": {}}
        show_dict = {"show": {}, "collections": {}}
        fetch_collections = not (single_movie or single_series)

        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
            except UnknownType as e:
                self.logger.error(f"Library '{library_name}' is invalid: {e}")
                continue

            if library.type == "movie" and not single_series:
                self._process_library(library, movie_dict, fetch_collections)
            if library.type == "show" and not single_movie:
                self._process_library(library, show_dict, fetch_collections)

        if single_movie:
            return movie_dict
        elif single_series:
            return show_dict
        else:
            return movie_dict, show_dict

    def _process_library(
        self,
        library: LibrarySection,
        item_dict: dict[str, dict],
        fetch_collections: bool = True,
    ) -> None:
        library_title = library.title

        if library_title not in item_dict[library.type]:
            item_dict[library.type][library_title] = {}
        if fetch_collections and library_title not in item_dict["collections"]:
            item_dict["collections"][library_title] = {}

        all_items = library.all()
        for item in all_items:
            title_key = item.title
            year = item.year or ""
            edition = getattr(item, "editionTitle", None)
            if edition:
                title_name = f"{title_key} ({year}) [{edition}]".strip()
            else:
                title_name = f"{title_key} ({year})".strip()

            item_dict[library.type][library_title][title_name] = item

        if fetch_collections:
            all_collections = library.collections()
            for collection in all_collections:
                collection_key = collection.title
                item_dict["collections"][library_title][collection_key] = collection

    def fetch_recently_added(self, media_type: str):
        recently_added_dict = {media_type: {}}
        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
                if library.type == media_type:
                    self.logger.debug(
                        f"Fetching recently added items from library: '{library.title}', Type: '{library.type}'"
                    )
                    recently_added = library.recentlyAdded(maxresults=5)
                    if recently_added:
                        if library_name not in recently_added_dict[media_type]:
                            recently_added_dict[media_type][library_name] = {}

                        for item in recently_added:
                            title_key = item.title
                            year = item.year or ""
                            title_name = f"{title_key} ({year})".strip()
                            recently_added_dict[media_type][library_name][
                                title_name
                            ] = item
                        self.logger.info(
                            f"Fetched {len(recently_added)} recently added items from '{library_name}'"
                        )
                    else:
                        self.logger.info(
                            f"No recently added items found in library '{library_name}'"
                        )
            except UnknownType as e:
                self.logger.error(f"Library '{library_name}' is invalid: {e}")
                continue
            except Exception as e:
                self.logger.error(
                    f"An error occurred while fetching recently added items from '{library_name}': {e}"
                )
        return recently_added_dict if recently_added_dict[media_type] else None
