from Payloads.poster_renamerr_payload import Payload as PosterRenamerPayload
from Payloads.unmatched_assets_payload import Payload as UnmatchedAssetsPayload

def get_instances(model) -> dict[str, dict[str, str]]: 
    instances = model.query.all()
    model_dict = {
        item.instance_name: {"url": item.url, "api": item.api_key} for item in instances
    }
    return model_dict

def create_poster_renamer_payload(radarr, sonarr, plex) -> PosterRenamerPayload:
    from daps_webui.models.settings import Settings
    settings = Settings.query.first()

    return PosterRenamerPayload(
        source_dirs=getattr(settings, 'source_dirs', '').split(",") if getattr(settings, 'source_dirs', None) else [],
        target_path=getattr(settings, 'target_path', ''),
        asset_folders=getattr(settings, 'asset_folders', False),
        unmatched_assets=getattr(settings, 'unmatched_assets', True),
        border_replacerr=getattr(settings, 'border_replacerr', False),
        library_names=getattr(settings, 'library_names', '').split(",") if getattr(settings, 'library_names', None) else [],
        instances=getattr(settings, 'instances', '').split(",") if getattr(settings, 'instances', None) else [],
        radarr=radarr,
        sonarr=sonarr,
        plex=plex,
    )

def create_unmatched_assets_payload(radarr, sonarr, plex) -> UnmatchedAssetsPayload:
    from daps_webui.models.settings import Settings
    settings = Settings.query.first()

    return UnmatchedAssetsPayload(
        target_path=getattr(settings, 'target_path', ''),
        asset_folders=getattr(settings, 'asset_folders', False),
        library_names=getattr(settings, 'library_names', '').split(",") if getattr(settings, 'library_names', None) else [],
        instances=getattr(settings, 'instances', '').split(",") if getattr(settings, 'instances', None) else [],
        radarr=radarr,
        sonarr=sonarr,
        plex=plex,
    )
