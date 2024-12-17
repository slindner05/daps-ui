import json
import sqlite3
from contextlib import closing
from logging import Logger

from DapsEX.settings import Settings


class Database:
    def __init__(self) -> None:
        self.initialize_db()

    def get_db_connection(self):
        conn = sqlite3.connect(Settings.DB_PATH.value)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self):
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT PRIMARY KEY,
                    file_name TEXT,
                    status TEXT DEFAULT NULL,
                    has_episodes INTEGER DEFAULT NULL,
                    has_file INTEGER DEFAULT NULL,
                    media_type TEXT, 
                    file_hash TEXT UNIQUE,
                    original_file_hash TEXT UNIQUE,
                    source_path TEXT,
                    border_replaced INTEGER DEFAULT 0,
                    webhook_run INTEGER DEFAULT NULL,
                    uploaded_to_libraries TEXT DEFAULT '[]',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_movies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_shows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT UNIQUE,
                        main_poster_missing INTEGER DEFAULT NULL 
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_seasons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        show_id INTEGER,
                        season TEXT,
                        FOREIGN KEY (show_id) REFERENCES unmatched_shows (id) ON DELETE CASCADE,
                        UNIQUE (show_id, season)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unmatched_stats (
                    id INTEGER PRIMARY KEY,
                    total_movies INTEGER DEFAULT 0,
                    total_series INTEGER DEFAULT 0,
                    total_seasons INTEGER DEFAULT 0,
                    total_collections INTEGER DEFAULT 0,
                    unmatched_movies INTEGER DEFAULT 0,
                    unmatched_series INTEGER DEFAULT 0,
                    unmatched_seasons INTEGER DEFAULT 0,
                    unmatched_collections INTEGER DEFAULT 0
                    )
                    """
                )
                conn.commit()

    def add_file(
        self,
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
        webhook_run: bool | None,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "INSERT OR REPLACE INTO file_cache (file_path, file_name, status, has_episodes, has_file, media_type, file_hash, original_file_hash, source_path, border_replaced, webhook_run) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                        webhook_run,
                    ),
                )
            conn.commit()

    def update_file(
        self,
        file_hash: str,
        original_file_hash: str,
        source_path: str,
        file_path: str,
        border_replaced: bool,
    ) -> None:
        with self.get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    "UPDATE file_cache SET file_hash = ?, original_file_hash = ?, source_path = ?, border_replaced = ?, uploaded_to_libraries = ? WHERE file_path = ?",
                    (
                        file_hash,
                        original_file_hash,
                        source_path,
                        int(border_replaced),
                        json.dumps([]),
                        file_path,
                    ),
                )
            conn.commit()

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
                        "uploaded_to_libraries": (
                            json.loads(uploaded_to_libraries)
                            if uploaded_to_libraries
                            else []
                        ),
                        "webhook_run": webhook_flag,
                        "timestamp": timestamp,
                    }
                    for file_path, file_name, status, has_episodes, has_file, media_type, file_hash, original_file_hash, source_path, border_replaced, webhook_flag, uploaded_to_libraries, timestamp, in result
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
