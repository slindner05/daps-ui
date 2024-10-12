from daps_webui import db

class FileCache(db.Model):
    __tablename__ = "file_cache"
    file_path = db.Column(db.String, primary_key=True)
    media_type = db.Column(db.String)
    file_hash = db.Column(db.String, unique=True)
    source_path = db.Column(db.String)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
