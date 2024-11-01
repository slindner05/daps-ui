from daps_webui import db

class Settings(db.Model):
    __tablename__ = "settings_table"
    id = db.Column(db.Integer, primary_key=True)
    poster_renamer_schedule = db.Column(db.String)
    target_path = db.Column(db.String)
    source_dirs = db.Column(db.String)
    library_names = db.Column(db.String)
    instances = db.Column(db.String)
    asset_folders = db.Column(db.Boolean, default=False, nullable=False)
    unmatched_assets = db.Column(db.Boolean, default=True, nullable=False)
    border_replacerr = db.Column(db.Boolean, default=False, nullable=False)
