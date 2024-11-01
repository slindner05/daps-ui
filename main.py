from DapsEX import PosterRenamerr, UnmatchedAssets, YamlConfig
from Payloads.poster_renamerr_payload import Settings


def run_renamer():
    config = YamlConfig(Settings.POSTER_RENAMERR.value)
    payload = config.create_poster_renamer_payload()
    renamerr = PosterRenamerr(payload.target_path, payload.source_dirs, payload.asset_folders, payload.border_replacerr)
    renamerr.run(payload)
    if payload.unmatched_assets:
       run_unmatched_assets() 

def run_unmatched_assets():
    config = YamlConfig(Settings.POSTER_RENAMERR.value)
    payload = config.create_unmatched_assets_payload()
    unmatched_assets = UnmatchedAssets(payload.target_path, payload.asset_folders)
    unmatched_assets.run(payload)

if __name__ == "__main__":
    run_renamer()
    # run_unmatched_assets()
