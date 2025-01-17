from logging import Logger

from sqlalchemy.exc import SQLAlchemyError

from daps_webui.models.file_cache import FileCache


class Database:
    def __init__(self, db, logger: Logger):
        self.logger = logger
        self.db = db

    def delete_file_cache_entry(self, file_path: str) -> bool:
        try:
            entry = (
                self.db.session.query(FileCache).filter_by(file_path=file_path).first()
            )
            if entry:
                self.db.session.delete(entry)
                self.db.session.commit()
                self.logger.debug(f"Deleted poster: {file_path} from database")
                return True
            return False
        except SQLAlchemyError as e:
            self.logger.error(f"Error deleting file cache entry: {e}")
            self.db.session.rollback()
            return False

    def get_first_file_settings(self) -> dict | None:
        try:
            first_entry = self.db.session.query(FileCache).first()
            if first_entry:
                self.logger.debug(
                    f"Found first file in file cache: {first_entry.file_path}"
                )
                return {
                    "border_setting": first_entry.border_setting,
                    "custom_color": first_entry.custom_color,
                }
            self.logger.debug("No files found in file cache")
            return None
        except SQLAlchemyError as e:
            self.logger.error(f"Error querying file cache: {e}")
