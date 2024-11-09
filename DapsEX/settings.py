from enum import Enum

class Settings(Enum):
    CONFIG_PATH = r"./config/config.yaml"
    LOG_DIR = r"./config/logs"
    POSTER_RENAMERR = "poster_renamerr"
    UNMATCHED_ASSETS = "unmatched_assets"
    DB_PATH = r"./config/db/database.db"
