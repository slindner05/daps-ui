from dataclasses import dataclass


@dataclass(slots=True)
class Payload:
    log_level: int
    client_id: str
    rclone_token: str
    rclone_secret: str
    service_account: str
    gdrives: list
