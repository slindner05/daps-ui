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
                    or "uploaded_to_libraries" not in columns
                ):
                    print(
                        "file_cache table is missing 'status' and/or 'has_episodes' and/or 'has_file' and/or 'webhook_run' and/or uploaded_to_libraries column"
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


def add_to_settings(db_path):
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(settings_table);")
                columns = [col[1] for col in cursor.fetchall()]

                missing_columns = [
                    col
                    for col in ["reapply_posters", "show_all_unmatched"]
                    if col not in columns
                ]

                if missing_columns:
                    for column in missing_columns:
                        print(
                            f"Adding new columns to settings_table: {missing_columns}"
                        )
                        cursor.execute(
                            f"ALTER TABLE settings_table ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0;"
                        )
                        conn.commit()
                        print("Successfully added new columns")
                else:
                    print("settings_table is already up to date")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    try:
        db_path = "/config/db/database.db"
        reset_file_cache(db_path)
        add_to_settings(db_path)
    except Exception as e:
        print(f"Unexpected error during initialization: {e}")
