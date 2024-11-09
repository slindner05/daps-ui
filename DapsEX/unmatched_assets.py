from DapsEX.logger import init_logger
from DapsEX.media import Server, Radarr, Sonarr, Media
from DapsEX.database_cache import Database
from DapsEX.settings import Settings
from Payloads.unmatched_assets_payload import Payload
from pathlib import Path
from DapsEX import utils
import re
from tabulate import tabulate
import logging
import json


class UnmatchedAssets:
    def __init__(self, assets_dir: str, asset_folders: bool, log_level=logging.info):
        try:
            log_dir = Path(Settings.LOG_DIR.value) / Settings.UNMATCHED_ASSETS.value
            self.assets_dir = Path(assets_dir)
            self.asset_folders = asset_folders
            self.db = Database()
            self.db.initialize_stats()
            self.logger = logging.getLogger("UnmatchedAssets")
            init_logger(self.logger, log_dir, "unmatched_assets", log_level=log_level)
        except Exception as e:
            self.logger.exception("Failed to initialize UnmatchedAssets")
            raise e

    def _log_banner(self):
        self.logger.info("\n" + "#" * 80)
        self.logger.info("### New UnmatchedAssets Run")
        self.logger.info("\n" + "#" * 80)

    def get_assets(self) -> list[str]:
        if not self.assets_dir.is_dir():
            self.logger.error(f"{self.assets_dir} is not a directory")
            raise ValueError
        return [item.stem for item in self.assets_dir.rglob("*") if item.is_file()]

    def get_assets_folders(self):
        assets = []
        if not self.assets_dir.is_dir():
            self.logger.error(f"{self.assets_dir} is not a directory")
            raise ValueError
        asset_paths = [
            Path(item) for item in self.assets_dir.rglob("*") if item.is_file()
        ]
        season_pattern = re.compile(r"Season\d{2}")
        for asset in asset_paths:
            if season_pattern.match(asset.stem):
                asset_name = f"{asset.parent.name}{asset.stem}"
                assets.append(asset_name)
            else:
                asset_name = f"{asset.parent.name}"
                assets.append(asset_name)
        return assets

    @staticmethod
    def _normalize_name(name: str) -> str:
        return utils.strip_id(utils.remove_chars(name))

    def get_show_assets_normalized(
        self,
        media_dict: dict[str, list[dict]],
        assets: list[str],
    ) -> list[str]:
        shows_dict_list = media_dict.get("shows", [])
        assets_normalized = [self._normalize_name(asset) for asset in assets]
        show_assets = []

        for asset in assets_normalized:
            season_asset = re.sub(r"season\d{2}", "", asset).strip()
            for item in shows_dict_list:
                normalized_title = self._normalize_name(item["title"])
                if normalized_title == asset or normalized_title == season_asset:
                    show_assets.append(asset)
        return show_assets

    def get_unmatched_assets(
        self,
        media_dict: dict[str, list[dict]],
        collections_dict: dict[str, list[str]],
        assets: list[str],
        show_assets_normalized: list[str],
    ) -> dict[str, list]:
        unmatched_assets = {"movies": [], "collections": [], "shows": []}

        movies_list_dict = media_dict.get("movies", [])
        shows_list_dict = media_dict.get("shows", [])
        assets_normalized = [self._normalize_name(asset) for asset in assets]

        for movie in movies_list_dict:
            movie_normalized = self._normalize_name(movie["title"])
            if movie_normalized not in assets_normalized:
                if movie["status"] in ["released"]:
                    unmatched_assets["movies"].append(movie["title"])
                    self.db.add_unmatched_movie(title=movie["title"])
                    self.logger.debug(
                        f"Added unmatched movie: {movie['title']} to database"
                    )
                else:
                    self.logger.debug(
                        f"Skipping {movie['title']} -> Status: {movie['status']}"
                    )

        for key, value_list in collections_dict.items():
            for collection in value_list:
                collection_normalized = self._normalize_name(collection)
                if collection_normalized not in assets_normalized:
                    unmatched_assets["collections"].append(collection)
                    self.db.add_unmatched_collection(title=collection)
                    self.logger.debug(
                        f"Added unmatched collection: {collection} to database"
                    )

        for item in shows_list_dict:
            show_normalized = self._normalize_name(item["title"])
            unmatched_show = {
                "title": utils.strip_id(item["title"]),
                "seasons": [],
                "main_poster_missing": False,
            }
            show_id = None
            if show_normalized not in show_assets_normalized:
                if item["status"] in ["released", "ended", "continuing"]:
                    show_id = self.db.add_unmatched_show(
                        title=unmatched_show["title"], main_poster_missing=True
                    )
                    unmatched_show["main_poster_missing"] = True
                else:
                    self.logger.debug(
                        f"Skipping show item: {item['title']} -> Status: {item['status']}"
                    )

            for season in item.get("seasons", []):
                season_asset = f"{show_normalized}{season['season']}"
                if season_asset not in show_assets_normalized and season.get(
                    "has_episodes", False
                ):
                    unmatched_show["seasons"].append(season["season"])
                    if show_id is None:
                        show_id = self.db.add_unmatched_show(
                            title=utils.strip_id(item["title"]),
                            main_poster_missing=False,
                        )
                    self.db.add_unmatched_season(
                        show_id=show_id, season=season["season"]
                    )
                elif not season.get("has_episodes", False):
                    self.logger.debug(
                        f"Skipping {utils.strip_id(item['title'])} - {season['season']} -> No episodes on disk"
                    )
            if unmatched_show["seasons"] or unmatched_show["main_poster_missing"]:
                unmatched_assets["shows"].append(unmatched_show)

        return unmatched_assets

    def cleanup_unmatched_media(self, new_unmatched_assets: dict[str, list]):
        current_unmatched_assets = self.db.get_all_unmatched_assets()

        self._cleanup_unmatched_movies(
            new_unmatched_assets["movies"], current_unmatched_assets["movies"]
        )
        self._cleanup_unmatched_collections(
            new_unmatched_assets["collections"], current_unmatched_assets["collections"]
        )
        self._cleanup_unmatched_show_seasons(
            new_unmatched_assets["shows"], current_unmatched_assets["shows"]
        )

    def _cleanup_unmatched_movies(
        self, new_unmatched_movies: list[str], current_unmatched_movies: list[dict]
    ):
        for movie in current_unmatched_movies:
            if movie["title"] not in new_unmatched_movies:
                self.db.delete_unmatched_asset(
                    db_table="unmatched_movies", title=movie["title"]
                )
                self.logger.debug(
                    f"Removed movie: {movie['title']} from unmatched database"
                )

    def _cleanup_unmatched_collections(
        self,
        new_unmatched_collections: list[str],
        current_unmatched_collections: list[dict],
    ):
        for collection in current_unmatched_collections:
            if collection["title"] not in new_unmatched_collections:
                self.db.delete_unmatched_asset(
                    db_table="unmatched_collections", title=collection["title"]
                )
                self.logger.debug(
                    f"Removed collection: {collection['title']} from unmatched database"
                )

    def _cleanup_unmatched_show_seasons(
        self, new_unmatched_shows: list[dict], current_unmatched_shows: list[dict]
    ):
        new_unmatched_lookup = {show["title"]: show for show in new_unmatched_shows}
        for show in current_unmatched_shows:
            show_title = show["title"]
            if show_title not in new_unmatched_lookup:
                self.db.delete_unmatched_asset(
                    db_table="unmatched_shows", title=show_title
                )
                self.logger.debug(f"Removed show: {show_title} from unmatched database")
                continue

            new_unmatched_show = new_unmatched_lookup[show_title]
            new_unmatched_seasons = set(new_unmatched_show.get("seasons", []))
            current_unmatched_seasons = set(show.get("seasons", []))
            seasons_to_delete = current_unmatched_seasons - new_unmatched_seasons

            for season in seasons_to_delete:
                self.db.delete_unmatched_season(show_id=show["id"], season=season)
                self.logger.debug(
                    f"Removed season: {season} for {show_title} from unmatched database"
                )

    def get_unmatched_count_dict(
        self,
        unmatched_assets: dict[str, list],
        media_dict: dict[str, list[dict]],
        collections_dict: dict[str, list[str]],
    ):
        asset_count_dict = {
            "total_movies": 0,
            "total_series": 0,
            "total_seasons": 0,
            "total_collections": 0,
            "unmatched_movies": 0,
            "unmatched_series": 0,
            "unmatched_seasons": 0,
            "unmatched_collections": 0,
        }

        shows_list = media_dict.get("shows", [])
        movies_list = media_dict.get("movies", [])

        total_movies = len(
            [movie for movie in movies_list if movie["status"] in ["released"]]
        )
        asset_count_dict["total_movies"] = total_movies

        total_shows = len(
            [
                show
                for show in shows_list
                if show["status"] in ["released", "ended", "continuing"]
            ]
        )
        asset_count_dict["total_series"] = total_shows

        total_seasons = sum(
            len(
                [
                    season
                    for season in show.get("seasons", [])
                    if season.get("has_episodes", False)
                ]
            )
            for show in shows_list
        )
        asset_count_dict["total_seasons"] = total_seasons

        total_collections = len(
            collections_dict.get("movies", []) + collections_dict.get("shows", [])
        )
        asset_count_dict["total_collections"] = total_collections

        unmatched_show_season_list = unmatched_assets.get("shows", [])
        unmatched_show_list = [
            show
            for show in unmatched_show_season_list
            if show.get("main_poster_missing", True)
        ]

        unmatched_movie_list = unmatched_assets.get("movies", [])
        unmatched_collection_list = unmatched_assets.get("collections", [])

        unmatched_movie_count = len(unmatched_movie_list)
        asset_count_dict["unmatched_movies"] = unmatched_movie_count

        unmatched_collection_count = len(unmatched_collection_list)
        asset_count_dict["unmatched_collections"] = unmatched_collection_count

        unmatched_show_count = len(unmatched_show_list)
        asset_count_dict["unmatched_series"] = unmatched_show_count

        unmatched_season_count = sum(
            len(show.get("seasons", [])) for show in unmatched_show_season_list
        )
        asset_count_dict["unmatched_seasons"] = unmatched_season_count

        self.db.update_stats(asset_count_dict)
        return asset_count_dict

    def print_output(
        self,
        asset_count_dict: dict[str, int],
        unmatched_assets: dict[str, list],
    ) -> None:
        total_movies = asset_count_dict.get("total_movies", 0)
        total_shows = asset_count_dict.get("total_series", 0)
        total_seasons = asset_count_dict.get("total_seasons", 0)
        total_collections = asset_count_dict.get("total_collections", 0)
        grand_total = total_movies + total_shows + total_seasons + total_collections

        unmatched_movie_count = asset_count_dict.get("unmatched_movies", 0)
        unmatched_show_count = asset_count_dict.get("unmatched_series", 0)
        unmatched_season_count = asset_count_dict.get("unmatched_seasons", 0)
        unmatched_collection_count = asset_count_dict.get("unmatched_collections", 0)
        unmatched_grand_total = (
            unmatched_movie_count
            + unmatched_show_count
            + unmatched_season_count
            + unmatched_collection_count
        )

        percent_complete_movies = (
            100 * (total_movies - unmatched_movie_count) / total_movies
            if total_movies
            else 0
        )
        percent_complete_shows = (
            100 * (total_shows - unmatched_show_count) / total_shows
            if total_shows
            else 0
        )
        percent_complete_seasons = (
            100 * (total_seasons - unmatched_season_count) / total_seasons
            if total_seasons
            else 0
        )
        percent_complete_collections = (
            100 * (total_collections - unmatched_collection_count) / total_collections
            if total_collections
            else 0
        )
        percent_complete_grand_total = (
            100 * (grand_total - unmatched_grand_total) / grand_total
            if grand_total
            else 0
        )

        unmatched_movie_list = unmatched_assets.get("movies", [])
        unmatched_show_season_list = unmatched_assets.get("shows", [])
        unmatched_collection_list = unmatched_assets.get("collections", [])

        if unmatched_movie_list:
            table_data = [["UNMATCHED MOVIES", ""]]
            for movie in unmatched_movie_list:
                table_data.append([movie])
            self.logger.info(
                "\n" + tabulate(table_data, headers="firstrow", tablefmt="fancy_grid")
            )

        if unmatched_show_season_list:
            table_data = [["UNMATCHED SHOWS AND SEASONS", ""]]

            for show in unmatched_show_season_list:
                show_clean = utils.strip_id(show["title"])
                missing_assets = []
                if show.get("main_poster_missing", True):
                    missing_assets.append("show poster")
                missing_seasons = [season for season in show.get("seasons", [])]
                missing_assets.extend(missing_seasons)
                missing_assets_str = ", ".join(missing_assets) or "None"
                table_data.append([show_clean, missing_assets_str])

            self.logger.info(
                "\n" + tabulate(table_data, headers="firstrow", tablefmt="fancy_grid")
            )

        if unmatched_collection_list:
            table_data = [["UNMATCHED COLLECTIONS", ""]]
            for collection in unmatched_collection_list:
                table_data.append([collection])
            self.logger.info(
                "\n" + tabulate(table_data, headers="firstrow", tablefmt="fancy_grid")
            )

        total_table_data = [
            [
                "Movies",
                total_movies,
                unmatched_movie_count,
                f"{percent_complete_movies:.2f}%",
            ],
            [
                "Series",
                total_shows,
                unmatched_show_count,
                f"{percent_complete_shows:.2f}%",
            ],
            [
                "Seasons",
                total_seasons,
                unmatched_season_count,
                f"{percent_complete_seasons:.2f}%",
            ],
            [
                "Collections",
                total_collections,
                unmatched_collection_count,
                f"{percent_complete_collections:.2f}%",
            ],
            [
                "Grand Total",
                grand_total,
                unmatched_grand_total,
                f"{percent_complete_grand_total:.2f}%",
            ],
        ]
        self.logger.info(
            "\n"
            + tabulate(
                total_table_data,
                headers=["Type", "Total", "Unmatched", "Percent Complete"],
                tablefmt="fancy_grid",
            )
        )

    def run(self, payload: Payload):
        from DapsEX import utils

        try:
            self._log_banner()
            media = Media()
            self.logger.debug("Creating Radarr Sonarr and Plex instances.")
            radarr_instances, sonarr_instances = utils.create_arr_instances(
                payload, Radarr, Sonarr, self.logger
            )
            plex_instances = utils.create_plex_instances(payload, Server, self.logger)
            self.logger.debug("Successfully created all instances.")

            self.logger.debug("Creating media and collections dict.")
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
            self.logger.debug("Created media dict and collections dict")
            if self.asset_folders:
                self.logger.debug("Getting all assets")
                self.logger.debug(f"Asset folders: {self.asset_folders}")
                assets = self.get_assets_folders()
                show_assets = self.get_show_assets_normalized(media_dict, assets)
            else:
                self.logger.debug("Getting all assets")
                self.logger.debug(f"Asset folders: {self.asset_folders}")
                assets = self.get_assets()
                show_assets = self.get_show_assets_normalized(media_dict, assets)

            self.logger.debug("Getting all unmatched assets and asset counts")
            unmatched_assets = self.get_unmatched_assets(
                media_dict, collections_dict, assets, show_assets
            )
            self.logger.debug(
                "Unmatched assets summary:\n%s", json.dumps(unmatched_assets, indent=4)
            )
            asset_count_dict = self.get_unmatched_count_dict(
                unmatched_assets, media_dict, collections_dict
            )
            self.logger.debug("Cleaning up database")

            self.cleanup_unmatched_media(unmatched_assets)
            self.print_output(asset_count_dict, unmatched_assets)
        except Exception as e:
            self.logger.exception("Failed to run UnmatchedAssets")
            raise e
