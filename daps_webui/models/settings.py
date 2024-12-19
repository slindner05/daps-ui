from daps_webui import db


class Settings(db.Model):
    __tablename__ = "settings_table"
    id = db.Column(db.Integer, primary_key=True)
    log_level_unmatched_assets = db.Column(db.String, default="info")
    log_level_poster_renamer = db.Column(db.String, default="info")
    poster_renamer_schedule = db.Column(db.String)
    unmatched_assets_schedule = db.Column(db.String)
    target_path = db.Column(db.String)
    source_dirs = db.Column(db.String)
    library_names = db.Column(db.String)
    instances = db.Column(db.String)
    asset_folders = db.Column(db.Boolean, default=False, nullable=False)
    unmatched_assets = db.Column(db.Boolean, default=True, nullable=False)
    border_replacerr = db.Column(db.Boolean, default=False, nullable=False)
    run_single_item = db.Column(db.Boolean, default=False, nullable=False)
    upload_to_plex = db.Column(db.Boolean, default=False, nullable=False)
    show_all_unmatched = db.Column(db.Boolean, default=False, nullable=False)
