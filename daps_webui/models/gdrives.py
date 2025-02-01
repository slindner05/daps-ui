from daps_webui import db


class GDrives(db.Model):
    __tablename__ = "gdrives"
    id = db.Column(db.Integer, primary_key=True)
    drive_name = db.Column(db.String, nullable=True)
    drive_id = db.Column(db.String, nullable=True)
    drive_location = db.Column(db.String, nullable=True)

    def __init__(self, drive_name: str, drive_id: str, drive_location: str) -> None:
        self.drive_name = drive_name
        self.drive_id = drive_id
        self.drive_location = drive_location
