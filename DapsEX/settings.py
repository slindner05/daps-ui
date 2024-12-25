from enum import Enum


class Settings(Enum):
    CONFIG_PATH = "/config/config.yaml"
    LOG_DIR = "/config/logs"
    POSTER_RENAMERR = "poster_renamerr"
    UNMATCHED_ASSETS = "unmatched_assets"
    PLEX_UPLOADERR = "plex_uploaderr"
    MAIN = "main"
    DB_PATH = "/config/db/database.db"
