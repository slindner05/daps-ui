from daps_webui import db


class RCloneConf(db.Model):
    __tablename__ = "rclone"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String, nullable=True)
    rclone_token = db.Column(db.String, nullable=True)
    rclone_secret = db.Column(db.String, nullable=True)
    service_account = db.Column(db.String, nullable=True)

    def __init__(
        self,
        client_id: str,
        rclone_token: str,
        rclone_secret: str,
        service_account: str,
    ) -> None:
        self.client_id = client_id
        self.rclone_token = rclone_token
        self.rclone_secret = rclone_secret
        self.service_account = service_account
