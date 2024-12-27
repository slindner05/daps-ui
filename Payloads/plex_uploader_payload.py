from dataclasses import dataclass


@dataclass(slots=True)
class Payload:
    log_level: int
    asset_folders: bool
    reapply_posters: bool
    library_names: list[str]
    instances: list[str]
    plex: dict[str, dict[str, str]]
    radarr: dict[str, dict[str, str]]
    sonarr: dict[str, dict[str, str]]
