import yaml
from pathlib import Path
from Payloads.poster_renamerr_payload import Payload as PosterRenamerPayload
from Payloads.unmatched_assets_payload import Payload as UnmatchedAssetsPayload
from DapsEX import Settings


class YamlConfig:
    def __init__(self, script_name: str, config_path=Settings.CONFIG_PATH.value):
        self.config_path = Path(config_path)
        self.script_name = script_name
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Config file not found at {self.config_path}")
            return
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return

        self.instances_config = config["instances"]
        self.script_config = config.get(f"{self.script_name}", "")
        self.radarr_config = self.instances_config.get("radarr", {})
        self.sonarr_config = self.instances_config.get("sonarr", {})
        self.plex_config = self.instances_config.get("plex", {})

    def create_poster_renamer_payload(self) -> PosterRenamerPayload:
        return PosterRenamerPayload(
            source_dirs=self.script_config.get("source_directories", []),
            target_path=self.script_config.get("target_directory", ""),
            asset_folders=self.script_config.get("asset_folders", False),
            unmatched_assets=self.script_config.get("unmatched_assets", True),
            border_replacerr=self.script_config.get("border_replacerr", False),
            library_names=self.script_config.get("library_names", []),
            instances=self.script_config.get("instances", []),
            radarr=self.radarr_config,
            sonarr=self.sonarr_config,
            plex=self.plex_config,
        )
    
    def create_unmatched_assets_payload(self) -> UnmatchedAssetsPayload:
        return UnmatchedAssetsPayload(
            target_path=self.script_config.get("target_directory", ""),
            asset_folders=self.script_config.get("asset_folders", False),
            library_names=self.script_config.get("library_names", []),
            instances=self.script_config.get("instances", []),
            radarr=self.radarr_config,
            sonarr=self.sonarr_config,
            plex=self.plex_config
        )
