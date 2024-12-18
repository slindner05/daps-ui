import logging
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from daps_webui.config.config import Config
from daps_webui.utils import webui_utils
from daps_webui.utils.logger_utils import init_logger
from daps_webui.utils.webui_utils import get_instances
from DapsEX.poster_renamerr import PosterRenamerr
from DapsEX.unmatched_assets import UnmatchedAssets
from progress import progress_instance

# all globals needs to be defined here
global_config = Config()
db = SQLAlchemy()
progress_dict = {}
executor = ThreadPoolExecutor(max_workers=1)

# define all loggers
daps_logger = logging.getLogger("daps-web")
log_level_str = getattr(global_config, "MAIN_LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str, logging.INFO)
init_logger(daps_logger, global_config.logs / "web-ui", "web_ui", log_level)
daps_logger.info("Logger initialized in main process")


def create_app() -> Flask:
    # init flask app
    app = Flask(__name__)
    app.config.from_object(global_config)

    # initiate database
    db.init_app(app)
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA journal_mode=WAL;"))
        daps_logger.info("WAL mode enabled for SQLite database")

    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        if app.debug:
            scheduler = BackgroundScheduler()
            if scheduler.running:
                scheduler.shutdown()
                daps_logger.info("Scheduler stopped in development server")

    with app.app_context():
        if app.debug:
            from daps_webui.utils.scheduler import schedule_jobs

            db.create_all()
            scheduler = BackgroundScheduler()
            schedule_jobs(scheduler)
            if not scheduler.running:
                scheduler.start()
                daps_logger.info("Scheduler started in development server")

    # import needed blueprints
    from daps_webui.views.home.home import home
    from daps_webui.views.poster_renamer.poster_renamer import poster_renamer
    from daps_webui.views.settings.settings import settings

    # register blueprints
    app.register_blueprint(home)
    app.register_blueprint(settings)
    app.register_blueprint(poster_renamer)

    return app


def run_renamer_task(webhook_item: dict | None = None):
    from daps_webui.models import PlexInstance, RadarrInstance, SonarrInstance

    try:
        radarr = get_instances(RadarrInstance())
        sonarr = get_instances(SonarrInstance())
        plex = get_instances(PlexInstance())
        poster_renamer_payload = webui_utils.create_poster_renamer_payload(
            radarr, sonarr, plex
        )
        daps_logger.debug(
            f"Unmatched assets flag: {poster_renamer_payload.unmatched_assets}"
        )

        job_id = progress_instance.add_job()
        daps_logger.info(f"Job Poster Renamerr: '{job_id}' added.")

        renamer = PosterRenamerr(
            poster_renamer_payload.target_path,
            poster_renamer_payload.source_dirs,
            poster_renamer_payload.asset_folders,
            poster_renamer_payload.border_replacerr,
            poster_renamer_payload.log_level,
        )

        if webhook_item:
            future = executor.submit(
                renamer.run,
                poster_renamer_payload,
                progress_instance,
                job_id,
                webhook_item,
            )
        else:
            future = executor.submit(
                renamer.run, poster_renamer_payload, progress_instance, job_id
            )

        if poster_renamer_payload.unmatched_assets:
            daps_logger.debug("Unmatched assets flag is true, setting up callback...")

            def run_unmatched_assets_callback(fut):
                handle_unmatched_assets_task(radarr, sonarr, plex)

            future.add_done_callback(run_unmatched_assets_callback)

        def remove_job_cb(fut):
            sleep(2)
            progress_instance.remove_job(job_id)
            daps_logger.info(f"Poster Renamerr Job: {job_id} has been removed")

        future.add_done_callback(remove_job_cb)

        return {
            "message": "Poster renamer task started",
            "job_id": job_id,
            "success": True,
        }
    except Exception as e:
        daps_logger.error(f"Error in Poster Renamer Task: {str(e)}")
        return {"success": False, "message": str(e)}


def handle_unmatched_assets_task(radarr, sonarr, plex):
    try:
        with app.app_context():
            unmatched_assets_payload = webui_utils.create_unmatched_assets_payload(
                radarr, sonarr, plex
            )
            job_id = progress_instance.add_job()
            daps_logger.info(f"Job Unmatched Assets: '{job_id}' added.")

            unmatched_assets = UnmatchedAssets(
                unmatched_assets_payload.target_path,
                unmatched_assets_payload.asset_folders,
                unmatched_assets_payload.log_level,
            )
            future = executor.submit(
                unmatched_assets.run,
                unmatched_assets_payload,
                progress_instance,
                job_id,
            )

            def remove_job_cb(fut):
                sleep(2)
                progress_instance.remove_job(job_id)
                daps_logger.info(f"Unmatched Assets Job: {job_id} has been removed")

            future.add_done_callback(remove_job_cb)
            return {
                "message": "Unmatched assets task started",
                "job_id": job_id,
                "success": True,
            }

    except Exception as e:
        daps_logger.error(f"Error in Unmatched Assets Task: {str(e)}")
        return {"success": False, "message": str(e)}


def run_unmatched_assets_task():
    from daps_webui.models import PlexInstance, RadarrInstance, SonarrInstance

    try:
        radarr = get_instances(RadarrInstance())
        sonarr = get_instances(SonarrInstance())
        plex = get_instances(PlexInstance())

        return handle_unmatched_assets_task(radarr, sonarr, plex)
    except Exception as e:
        return {"success": False, "message": str(e)}


app = create_app()
