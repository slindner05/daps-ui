import logging

from Payloads.border_replacerr_payload import Payload as BorderReplacerPayload
from Payloads.plex_uploader_payload import Payload as PlexUploaderPayload
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
    border_setting = settings.border_setting if settings else None
    if border_setting == "black":
        custom_color = "#000000"
    else:
        custom_color = settings.custom_color if settings else ""

    return PosterRenamerPayload(
        log_level=log_level,
        source_dirs=(
            getattr(settings, "source_dirs", "").split(",")
            if getattr(settings, "source_dirs", None)
            else []
        ),
        target_path=settings.target_path if settings else "",
        asset_folders=bool(settings.asset_folders) if settings else False,
        clean_assets=bool(settings.clean_assets) if settings else False,
        unmatched_assets=bool(settings.unmatched_assets) if settings else True,
        replace_border=bool(settings.replace_border) if settings else False,
        border_setting=border_setting,
        custom_color=custom_color,
        upload_to_plex=bool(settings.upload_to_plex) if settings else False,
        match_alt=bool(settings.match_alt) if settings else False,
        reapply_posters=bool(settings.reapply_posters) if settings else False,
        library_names=settings.library_names.split(",") if settings else [],
        instances=settings.instances.split(",") if settings else [],
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
        target_path=settings.target_path if settings else "",
        asset_folders=bool(settings.asset_folders) if settings else False,
        show_all_unmatched=settings.show_all_unmatched if settings else False,
        library_names=settings.library_names.split(",") if settings else [],
        instances=settings.instances.split(",") if settings else [],
        radarr=radarr,
        sonarr=sonarr,
        plex=plex,
    )


def create_plex_uploader_payload(radarr, sonarr, plex) -> PlexUploaderPayload:
    from daps_webui.models.settings import Settings

    settings = Settings.query.first()
    log_level_str = getattr(settings, "log_level_plex_uploaderr", "").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

    return PlexUploaderPayload(
        log_level=log_level,
        asset_folders=bool(settings.asset_folders) if settings else False,
        reapply_posters=bool(settings.reapply_posters) if settings else False,
        library_names=settings.library_names.split(",") if settings else [],
        instances=settings.instances.split(",") if settings else [],
        plex=plex,
        radarr=radarr,
        sonarr=sonarr,
    )


def create_border_replacer_payload() -> BorderReplacerPayload:
    from daps_webui.models.settings import Settings

    settings = Settings.query.first()
    log_level_str = getattr(settings, "log_level_border_replacerr", "").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

    border_setting = settings.border_setting if settings else None
    if border_setting == "black":
        custom_color = "#000000"
    else:
        custom_color = settings.custom_color if settings else ""

    return BorderReplacerPayload(
        log_level=log_level,
        asset_folders=bool(settings.asset_folders) if settings else False,
        target_path=settings.target_path if settings else "",
        border_setting=border_setting,
        custom_color=custom_color,
    )
