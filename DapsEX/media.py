from pathlib import Path
from typing import Any
from arrapi.apis.sonarr import Series
from arrapi.objs.reload import Movie
from plexapi.collection import LibrarySection
from plexapi.server import PlexServer
from arrapi import SonarrAPI, RadarrAPI
import re

class Media:
    @staticmethod
    def _get_paths(all_media_objects: list[Movie] | list[Series]) -> list[Path]:
        """
        Method to get paths from media objects (movies or series).
        """
        return [Path(item.path) for item in all_media_objects]  # type: ignore

    def get_dicts(
        self,
        movies_list: list[dict[str, Any]],
        series_list: list[Path],
        movies_collection_list: list[str],
        series_collection_list: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """
        Combines all unique movies, series and collections into dictionaries.
        """
        media_dict = {"movies": [], "shows": []}
        collections_dict = {"movies": [], "shows": []}
        series_name_list = [item.name for item in series_list]
        unique_movies = set()
        unique_shows = set()
        unique_movie_collections = set()
        unique_show_collections = set()

        for movie in movies_list:
            self._process_list(movie, unique_movies, media_dict, key="movies")
        for show in series_name_list:
            self._process_list(show, unique_shows, media_dict, key="shows")
        for collection in movies_collection_list:
            self._process_list(
                collection, unique_movie_collections, collections_dict, key="movies"
            )
        for collection in series_collection_list:
            self._process_list(
                collection, unique_show_collections, collections_dict, key="shows"
            )
        return media_dict, collections_dict

    def get_movies_with_years(self, all_movie_objects: list[Movie]) -> list[dict[str, Any]]:
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
                "years": []
            }

            path = Path(media_object.path) #type: ignore
            title = path.name 
            years = [
                extract_year(media_object.physicalRelease),
                extract_year(media_object.digitalRelease),
                extract_year(media_object.inCinemas)
            ]
            dict_with_years["title"] = title
            for year in years:
                if year and year not in dict_with_years["years"]:
                    dict_with_years["years"].append(year)

            titles_with_years.append(dict_with_years)
        return titles_with_years

    @staticmethod
    def _process_list(
        item: str | dict, unique_set: set, final_dict: dict, key: str
    ) -> None:
        if isinstance(item, dict):
            if item["title"] not in unique_set:
                unique_set.add(item["title"])
                final_dict[key].append(item)
        else:
            if item not in unique_set:
                unique_set.add(item)
                final_dict[key].append(item)


class Radarr(Media):
    def __init__(self, base_url: str, api: str):
        super().__init__()
        self.radarr = RadarrAPI(base_url, api)
        self.all_movie_objects = self.get_all_movies()
        self.movies = self.get_movies_with_years(self.all_movie_objects)

    def get_all_movies(self) -> list[Movie]:
        return self.radarr.all_movies()

class Sonarr(Media):
    def __init__(self, base_url: str, api: str):
        super().__init__()
        self.sonarr = SonarrAPI(base_url, api)
        self.all_series_objects = self.get_all_series()
        self.series = self._get_paths(self.all_series_objects)

    def get_all_series(self) -> list[Series]:
        return self.sonarr.all_series()

class Server:
    def __init__(self, plex_url: str, plex_token: str, library_names: list[str]):
        self.plex = PlexServer(plex_url, plex_token)
        self.library_names = library_names
        self.movie_collections, self.series_collections = self.get_collections()

    def get_collections(self) -> tuple[list, list]:
        movie_collections_list = []
        show_collections_list = []
        unique_collections = set()

        for library_name in self.library_names:
            try:
                library = self.plex.library.section(library_name)
            except Exception as e:
                print(f"Library '{library_name}' not found: {e}")
                continue

            if library.type == "movie":
                self._movie_collection(
                    library, library_name, unique_collections, movie_collections_list
                )
            if library.type == "show":
                self._show_collection(
                    library, library_name, unique_collections, show_collections_list
                )
        return movie_collections_list, show_collections_list

    def _movie_collection(
        self,
        library: LibrarySection,
        library_name: str,
        unique_collections: set,
        movie_collections_list: list[str],
    ) -> None:
        collections = library.collections()
        print(f"Processing collections from {library_name}")
        for collection in collections:
            if collection.title not in unique_collections:
                unique_collections.add(collection.title)
                movie_collections_list.append(collection.title)

    def _show_collection(
        self,
        library: LibrarySection,
        library_name: str,
        unique_collections: set,
        show_collections_list: list[str],
    ) -> None:
        collections = library.collections()
        print(f"Processing collections from {library_name}")
        for collection in collections:
            if collection.title not in unique_collections:
                unique_collections.add(collection.title)
                show_collections_list.append(collection.title)

