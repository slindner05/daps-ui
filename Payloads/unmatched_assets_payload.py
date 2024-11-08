from dataclasses import dataclass

@dataclass(slots=True)
class Payload:
    log_level: int
    target_path: str 
    asset_folders: bool
    library_names: list[str]
    instances: list[str]
    radarr: dict[str, dict[str, str]]
    sonarr: dict[str, dict[str, str]]
    plex: dict[str, dict[str, str]]
