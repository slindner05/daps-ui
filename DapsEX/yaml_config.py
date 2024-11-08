import json
import logging
from pathlib import Path

import yaml

from DapsEX.logger import init_logger
from DapsEX.settings import Settings
from Payloads.poster_renamerr_payload import Payload as PosterRenamerPayload
from Payloads.unmatched_assets_payload import Payload as UnmatchedAssetsPayload

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


class YamlConfig:
    def __init__(
        self,
        script_name: str,
        config_path=Settings.CONFIG_PATH.value,
        log_level=logging.INFO,
    ):
        log_dir = Path(Settings.LOG_DIR.value) / "yaml"
        self.logger = logging.getLogger("Yaml")
        init_logger(self.logger, log_dir, "yaml_config", log_level=log_level)
        self.config_path = Path(config_path)
        self.script_name = script_name
        self.load_config()
        self.logger.info("Yaml config initialized.")

    def load_config(self):
        try:
            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
        except FileNotFoundError as e:
            self.logger.error(f"Config file not found at {self.config_path}")
            raise e
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing config file: {e}")
            raise e

        self.log_level_config = config["log_level"]
        self.instances_config = config["instances"]
        self.script_config = config.get(f"{self.script_name}", "")
        self.radarr_config = self.instances_config.get("radarr", {})
        self.sonarr_config = self.instances_config.get("sonarr", {})
        self.plex_config = self.instances_config.get("plex", {})

    def create_poster_renamer_payload(self) -> PosterRenamerPayload:
        log_level_str = self.log_level_config.get("poster_renamerr", "INFO").upper()
        log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

        payload_data = {
            "log_level": log_level,
            "source_dirs": self.script_config.get("source_directories", []),
            "target_path": self.script_config.get("target_directory", ""),
            "asset_folders": self.script_config.get("asset_folders", False),
            "unmatched_assets": self.script_config.get("unmatched_assets", True),
            "border_replacerr": self.script_config.get("border_replacerr", False),
            "library_names": self.script_config.get("library_names", []),
            "instances": self.script_config.get("instances", []),
            "radarr": self.radarr_config,
            "sonarr": self.sonarr_config,
            "plex": self.plex_config,
        }
        self.logger.debug("===" * 10 + " PosterRenamerr Payload " + "===" * 10)
        self.logger.debug(json.dumps(payload_data, indent=4))

        return PosterRenamerPayload(**payload_data)

    def create_unmatched_assets_payload(self) -> UnmatchedAssetsPayload:
        log_level_str = self.log_level_config.get("unmatched_assets", "INFO").upper()
        log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

        payload_data = {
            "log_level": log_level,
            "target_path": self.script_config.get("target_directory", ""),
            "asset_folders": self.script_config.get("asset_folders", False),
            "library_names": self.script_config.get("library_names", []),
            "instances": self.script_config.get("instances", []),
            "radarr": self.radarr_config,
            "sonarr": self.sonarr_config,
            "plex": self.plex_config,
        }

        self.logger.debug("===" * 10 + " UnmatchedAssets Payload " + "===" * 10)
        self.logger.debug(json.dumps(payload_data, indent=4))

        return UnmatchedAssetsPayload(**payload_data)
