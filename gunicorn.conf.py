import os

# accesslog = "/config/logs/web-ui/web_ui_debug.log"
# errorlog = "/config/logs/web-ui/web_ui_debug.log"
# loglevel = "debug"


def on_starting(server):
    from daps_webui import app, daps_logger, db

    with app.app_context():
        version = os.getenv("VERSION", "0.0.1")
        daps_logger.info(f"Starting daps-ui v{version}")
        daps_logger.info("Initializing database schema...")
        db.create_all()
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA journal_mode=WAL;"))
        daps_logger.info("WAL mode enabled for SQLite database")
