import logging

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


def get_instances(model) -> dict[str, dict[str, str]]:
    instances = model.query.all()
    model_dict = {
        item.instance_name: {"url": item.url, "api": item.api_key} for item in instances
    }
    return model_dict


def create_poster_renamer_payload(radarr, sonarr, plex) -> PosterRenamerPayload:
    from daps_webui.models.settings import Settings

    settings = Settings.query.first()
    log_level_str = getattr(settings, "log_level_poster_renamer", "").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

    return PosterRenamerPayload(
        log_level=log_level,
        source_dirs=(
            getattr(settings, "source_dirs", "").split(",")
            if getattr(settings, "source_dirs", None)
            else []
        ),
        target_path=getattr(settings, "target_path", ""),
        asset_folders=getattr(settings, "asset_folders", False),
        unmatched_assets=getattr(settings, "unmatched_assets", True),
        border_replacerr=getattr(settings, "border_replacerr", False),
        upload_to_plex=getattr(settings, "upload_to_plex", False),
        reapply_posters=getattr(settings, "reapply_posters", False),
        library_names=(
            getattr(settings, "library_names", "").split(",")
            if getattr(settings, "library_names", None)
            else []
        ),
        instances=(
            getattr(settings, "instances", "").split(",")
            if getattr(settings, "instances", None)
            else []
        ),
        radarr=radarr,
        sonarr=sonarr,
        plex=plex,
    )


def create_unmatched_assets_payload(radarr, sonarr, plex) -> UnmatchedAssetsPayload:
    from daps_webui.models.settings import Settings

    settings = Settings.query.first()
    log_level_str = getattr(settings, "log_level_unmatched_assets", "").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

    return UnmatchedAssetsPayload(
        log_level=log_level,
        target_path=getattr(settings, "target_path", ""),
        asset_folders=getattr(settings, "asset_folders", False),
        show_all_unmatched=getattr(settings, "show_all_unmatched", False),
        library_names=(
            getattr(settings, "library_names", "").split(",")
            if getattr(settings, "library_names", None)
            else []
        ),
        instances=(
            getattr(settings, "instances", "").split(",")
            if getattr(settings, "instances", None)
            else []
        ),
        radarr=radarr,
        sonarr=sonarr,
        plex=plex,
    )
