import os
import sqlite3


def reset_file_cache(db_path):
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(file_cache);")
                columns = [col[1] for col in cursor.fetchall()]

                if (
                    "status" not in columns
                    or "has_episodes" not in columns
                    or "has_file" not in columns
                    or "webhook_run" not in columns
                ):
                    print(
                        "file_cache table is missing 'status' and/or 'has_episodes' and/or 'has_file' and/or 'webhook_run' column"
                    )
                    cursor.execute("DROP TABLE IF EXISTS file_cache")
                    conn.commit()
                    print("Dropped existing file_cache table")
                else:
                    print("file_cache table is already up to date")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    try:
        db_path = "/config/db/database.db"
        print(f"Resetting file_cache table in database: {db_path}")
        reset_file_cache(db_path)
    except Exception as e:
        print(f"Unexpected error during initialization: {e}")
