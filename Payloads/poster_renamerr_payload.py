from dataclasses import dataclass


@dataclass(slots=True)
class Payload:
    log_level: int
    source_dirs: list[str]
    target_path: str
    asset_folders: bool
    unmatched_assets: bool
    border_replacerr: bool
    upload_to_plex: bool
    reapply_posters: bool
    library_names: list[str]
    instances: list[str]
    radarr: dict[str, dict[str, str]]
    sonarr: dict[str, dict[str, str]]
    plex: dict[str, dict[str, str]]
