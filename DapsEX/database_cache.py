import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from logging import Logger
from pathlib import Path

from DapsEX.settings import Settings


class Database:
    def __init__(self) -> None:
        self.initialize_db()

    def get_db_connection(self):
        conn = sqlite3.connect(Settings.DB_PATH.value)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize_db(self):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT NOT NULL PRIMARY KEY,
                    file_name TEXT,
                    status TEXT,
                    has_episodes INTEGER,
                    has_file INTEGER,
                    media_type TEXT, 
                    file_hash TEXT,
                    original_file_hash TEXT,
                    source_path TEXT,
                    border_replaced INTEGER NOT NULL DEFAULT 0,
                    border_color TEXT,
                    webhook_run INTEGER,
                    uploaded_to_libraries TEXT NOT NULL DEFAULT '[]'
                )
                """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_movies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_shows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE NOT NULL,
                        main_poster_missing INTEGER NOT NULL DEFAULT 0  
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_seasons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        show_id INTEGER NOT NULL,
                        season TEXT NOT NULL,
                        FOREIGN KEY (show_id) REFERENCES unmatched_shows (id) ON DELETE CASCADE,
                        UNIQUE (show_id, season)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_stats (
                    id INTEGER PRIMARY KEY,
                    total_movies INTEGER NOT NULL DEFAULT 0,
                    total_series INTEGER NOT NULL DEFAULT 0,
                    total_seasons INTEGER NOT NULL DEFAULT 0,
                    total_collections INTEGER NOT NULL DEFAULT 0,
                    unmatched_movies INTEGER NOT NULL DEFAULT 0,
                    unmatched_series INTEGER NOT NULL DEFAULT 0,
                    unmatched_seasons INTEGER NOT NULL DEFAULT 0,
                    unmatched_collections INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.commit()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS webhook_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_type TEXT NOT NULL,
                        item_name TEXT NOT NULL,
                        timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (item_type, item_name)
                    )
                    """
                )
                conn.commit()

    def add_file(
        self,
        logger: Logger,
        file_path: str,
        file_name: str,
        status: str | None,
        has_episodes: bool | None,
        has_file: bool | None,
        media_type: str,
        file_hash: str,
        original_file_hash: str,
        source_path: str,
        border_replaced: bool,
        border_color: str | None = None,
        webhook_run: bool | None = None,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "SELECT 1 FROM file_cache WHERE file_path = ?",
                        (file_path,),
                    )
                    uploaded_to_libraries = json.dumps([])
                    row_exists = cursor.fetchone() is not None
                    cursor.execute(
                        "INSERT OR REPLACE INTO file_cache (file_path, file_name, status, has_episodes, has_file, media_type, file_hash, original_file_hash, source_path, border_replaced, border_color, webhook_run, uploaded_to_libraries) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            file_path,
                            file_name,
                            status,
                            has_episodes,
                            has_file,
                            media_type,
                            file_hash,
                            original_file_hash,
                            source_path,
                            border_replaced,
                            border_color,
                            webhook_run,
                            uploaded_to_libraries,
                        ),
                    )
                    conn.commit()
                    if row_exists:
                        logger.info(
                            f"File '{file_path}' was successfully updated in file cache."
                        )
                    else:
                        logger.debug(
                            f"File '{file_path}' was successfully added to file cache."
                        )
                except Exception as e:
                    logger.error(f"Failed to add file '{file_path}' to database: {e}")

    def is_duplicate_webhook(
        self, logger: Logger, new_item, cache_duration=600
    ) -> bool:

        item_name = Path(new_item["item_path"]).stem
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=cache_duration)

        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "DELETE FROM webhook_cache WHERE timestamp < ?", (cutoff,)
                    )
                    expired_count = cursor.rowcount
                    logger.debug(f"Expired webhooks removed: {expired_count}")

                    cursor.execute(
                        "SELECT 1 FROM webhook_cache WHERE item_type = ? AND item_name = ?",
                        (
                            new_item["type"],
                            item_name,
                        ),
                    )
                    if cursor.fetchone():
                        logger.debug(f"Duplicate webhook detected: {item_name}")
                        return True

                    cursor.execute(
                        "INSERT INTO webhook_cache (item_type, item_name, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
                        (new_item["type"], item_name),
                    )
                    logger.debug(f"New webhook added to cache: {item_name}")
                    conn.commit()

                except sqlite3.InternalError as e:
                    logger.debug(f"IntegrityError: {e}")
                    return True
        return False

    def update_file(
        self,
        logger: Logger,
        file_hash: str,
        original_file_hash: str,
        source_path: str,
        file_path: str,
        border_replaced: bool,
        border_color: str | None = None,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "UPDATE file_cache SET file_hash = ?, original_file_hash = ?, source_path = ?, border_replaced = ?, border_color = ?, uploaded_to_libraries = ? WHERE file_path = ?",
                        (
                            file_hash,
                            original_file_hash,
                            source_path,
                            int(border_replaced),
                            border_color,
                            json.dumps([]),
                            file_path,
                        ),
                    )
                    conn.commit()
                    logger.debug(
                        f"File '{file_path}' was successfully updated in file cache."
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to update file '{file_path}' to database: {e}"
                    )

    def update_status(self, file_path: str, status: str, logger):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "UPDATE file_cache SET status = ? WHERE file_path = ?",
                        (
                            status,
                            file_path,
                        ),
                    )
                    rows_updated = cursor.rowcount
                    if rows_updated == 0:
                        logger.warning(
                            f"No matching row found for file_path: {file_path}. Update skipped."
                        )
                    else:
                        logger.debug(
                            f"Succesfully updated 'status' to {status} for {file_path}"
                        )
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed to updated 'status' for {file_path}: {e}")

    def update_has_episodes(self, file_path: str, has_episodes: bool, logger):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "UPDATE file_cache SET has_episodes = ? WHERE file_path = ?",
                        (
                            int(has_episodes),
                            file_path,
                        ),
                    )
                    rows_updated = cursor.rowcount
                    if rows_updated == 0:
                        logger.warning(
                            f"No matching row found for file_path: {file_path}. Update skipped."
                        )
                    else:
                        logger.debug(
                            f"Succesfully updated 'has_episodes' to {has_episodes} for {file_path}"
                        )
                    conn.commit()
                except Exception as e:
                    logger.error(
                        f"Failed to updated 'has_episodes' for {file_path}: {e}"
                    )

    def update_has_file(self, file_path: str, has_file: bool, logger):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "UPDATE file_cache SET has_file = ? WHERE file_path = ?",
                        (
                            int(has_file),
                            file_path,
                        ),
                    )
                    rows_updated = cursor.rowcount
                    if rows_updated == 0:
                        logger.warning(
                            f"No matching row found for file_path: {file_path}. Update skipped."
                        )
                    else:
                        logger.debug(
                            f"Succesfully updated 'has_file' to {has_file} for {file_path}"
                        )
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed to updated 'has_file' for {file_path}: {e}")

    def update_uploaded_to_libraries(
        self, file_path: str, new_libraries: list, logger: Logger
    ):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "SELECT uploaded_to_libraries FROM file_cache WHERE file_path = ?",
                        (file_path,),
                    )
                    result = cursor.fetchone()
                    if not result:
                        logger.warning(
                            f"No matching row found for file_path: {file_path}. Update skipped"
                        )
                        return
                    current_libraries = json.loads(result[0]) if result[0] else []
                    updated_libraries = list(set(current_libraries + new_libraries))
                    cursor.execute(
                        "UPDATE file_cache SET uploaded_to_libraries = ? WHERE file_path = ?",
                        (
                            json.dumps(updated_libraries),
                            file_path,
                        ),
                    )
                    rows_updated = cursor.rowcount
                    if rows_updated > 0:
                        logger.debug(
                            f"Successfully updated 'uploaded_to_libraries' for {file_path} with libraries: {updated_libraries}"
                        )
                        conn.commit()
                    else:
                        logger.warning(
                            f"Failed to update 'uploaded_to_libraries' for file_path: {file_path}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to update 'uploaded_to_libraries' for {file_path}: {e}"
                    )

    def update_webhook_flag(self, file_path: str, logger: Logger, new_value=None):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    cursor.execute(
                        "UPDATE file_cache SET webhook_run = ? WHERE file_path = ?",
                        (
                            new_value,
                            file_path,
                        ),
                    )
                    rows_updated = cursor.rowcount
                    if rows_updated == 0:
                        logger.warning(
                            f"No matching row found for file_path: {file_path}. Update skipped."
                        )
                    else:
                        logger.debug(
                            f"Succesfully updated 'webhook_run' to {new_value} for {file_path}"
                        )
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed to update 'webhook_run' for {file_path}: {e}")

    def clear_uploaded_to_libraries_data(
        self, logger: Logger, webhook_run: bool | None = None
    ):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                try:
                    if webhook_run is True:
                        cursor.execute(
                            "UPDATE file_cache SET uploaded_to_libraries = ? WHERE webhook_run = ?",
                            ("[]", 1),
                        )
                    else:
                        cursor.execute(
                            "UPDATE file_cache SET uploaded_to_libraries = ?",
                            ("[]",),
                        )
                    conn.commit()
                    logger.debug("Successfully reset uploaded_to_libraries to '[]'")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to clear uploaded_to_libraries data: {e}")

    def get_cached_file(self, file_path: str) -> dict[str, str] | None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "SELECT * FROM file_cache WHERE file_path = ?", (file_path,)
                )
                result = cursor.fetchone()
                if result:
                    return dict(result)
                else:
                    return None

    def delete_cached_file(self, file_path: str) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "DELETE FROM file_cache WHERE file_path = ?", (file_path,)
                )
                conn.commit()

    def return_all_files(self, webhook_run: bool | None = None) -> dict[str, dict]:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                if webhook_run is True:
                    cursor.execute("SELECT * FROM file_cache WHERE webhook_run = 1")
                else:
                    cursor.execute("SELECT * FROM file_cache")

                result = cursor.fetchall()
                return {
                    file_path: {
                        "file_name": file_name,
                        "status": status,
                        "has_episodes": has_episodes,
                        "has_file": has_file,
                        "media_type": media_type,
                        "file_hash": file_hash,
                        "original_file_hash": original_file_hash,
                        "source_path": source_path,
                        "border_replaced": border_replaced,
                        "border_color": border_color,
                        "uploaded_to_libraries": (
                            json.loads(uploaded_to_libraries)
                            if uploaded_to_libraries
                            else []
                        ),
                        "webhook_run": webhook_flag,
                    }
                    for file_path, file_name, status, has_episodes, has_file, media_type, file_hash, original_file_hash, source_path, border_replaced, border_color, webhook_flag, uploaded_to_libraries in result
                }

    def add_unmatched_movie(
        self,
        title: str,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "SELECT id FROM unmatched_movies WHERE title = ?", (title,)
                )
                existing = cursor.fetchone()
                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO unmatched_movies (title)
                        VALUES (?)
                        """,
                        (title,),
                    )
            conn.commit()

    def add_unmatched_collection(
        self,
        title: str,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "SELECT id FROM unmatched_collections WHERE title = ?", (title,)
                )
                existing = cursor.fetchone()
                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO unmatched_collections (title)
                        VALUES (?)
                        """,
                        (title,),
                    )
            conn.commit()

    def add_unmatched_show(self, title: str, main_poster_missing: bool) -> int:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "SELECT id, main_poster_missing FROM unmatched_shows WHERE title = ?",
                    (title,),
                )
                existing = cursor.fetchone()
                show_id = None
                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO unmatched_shows (title, main_poster_missing)
                        VALUES (?, ?)
                        """,
                        (title, int(main_poster_missing)),
                    )
                    show_id = cursor.lastrowid
                else:
                    show_id, current_main_poster_missing = existing
                    if current_main_poster_missing != int(main_poster_missing):
                        cursor.execute(
                            """
                            UPDATE unmatched_shows
                            SET main_poster_missing = ?
                            WHERE id = ?
                            """,
                            (int(main_poster_missing), show_id),
                        )
            conn.commit()

        if show_id is None:
            raise ValueError("Failed to insert unmatched show into the database.")
        return show_id

    def add_unmatched_season(self, show_id: int, season: str) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "SELECT id FROM unmatched_seasons WHERE show_id = ? AND season = ?",
                    (show_id, season),
                )
                existing = cursor.fetchone()
                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO unmatched_seasons (show_id, season)
                        VALUES (?, ?)
                        """,
                        (show_id, season),
                    )
            conn.commit()

    def get_unmatched_assets(self, db_table: str) -> list[dict[str, str]]:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                if db_table == "unmatched_shows":
                    cursor.execute(
                        """
                    SELECT unmatched_shows.id, unmatched_shows.title, unmatched_shows.main_poster_missing, unmatched_seasons.season
                    FROM unmatched_shows
                    LEFT JOIN unmatched_seasons ON unmatched_shows.id = unmatched_seasons.show_id
                """
                    )
                    results = cursor.fetchall()
                    unmatched_shows = {}
                    for row in results:
                        show_id = row["id"]
                        if show_id not in unmatched_shows:
                            unmatched_shows[show_id] = {
                                "id": show_id,
                                "title": row["title"],
                                "main_poster_missing": bool(row["main_poster_missing"]),
                                "seasons": [],
                            }
                        if row["season"]:
                            unmatched_shows[show_id]["seasons"].append(row["season"])
                    return list(unmatched_shows.values())
                else:
                    cursor.execute(f"SELECT * FROM {db_table}")
                    results = cursor.fetchall()
                return [dict(result) for result in results]

    def get_all_unmatched_assets(self):
        unmatched_media = {
            "movies": self.get_unmatched_assets("unmatched_movies"),
            "shows": self.get_unmatched_assets("unmatched_shows"),
            "collections": self.get_unmatched_assets("unmatched_collections"),
        }
        return unmatched_media

    def delete_unmatched_asset(self, db_table, title):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(f"DELETE FROM {db_table} WHERE title = ?", (title,))
            conn.commit()

    def delete_unmatched_season(self, show_id: int, season: str):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    """
                    DELETE FROM unmatched_seasons
                    WHERE show_id = ? AND season = ?
                    """,
                    (show_id, season),
                )
                conn.commit()

    def wipe_unmatched_assets(self):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute("DELETE FROM unmatched_movies")
                cursor.execute("DELETE FROM unmatched_collections")
                cursor.execute("DELETE FROM unmatched_shows")
                cursor.execute("DELETE FROM unmatched_seasons")
                conn.commit()

    def initialize_stats(self) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    """
                    INSERT INTO unmatched_stats (id, total_movies, total_series, total_seasons, total_collections, unmatched_movies, unmatched_series, unmatched_seasons, unmatched_collections)
                    VALUES (1, 0, 0, 0, 0, 0, 0, 0, 0)
                    ON CONFLICT(id) DO NOTHING
                    """
                )

    def update_stats(self, stats: dict[str, int]) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                columns = ", ".join(f"{key} = ?" for key in stats.keys())
                values = tuple(stats.values())
                full_values = values + values

                cursor.execute(
                    f"""
                    INSERT INTO unmatched_stats (id, {", ".join(stats.keys())})
                    VALUES (1, {", ".join("?" for _ in stats.keys())})
                    ON CONFLICT(id)
                    DO UPDATE SET {columns}
                    """,
                    full_values,
                )
                conn.commit()
