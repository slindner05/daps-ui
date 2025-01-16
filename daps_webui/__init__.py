import logging
from concurrent.futures import ThreadPoolExecutor
from pprint import pformat
from time import sleep

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from daps_webui.config.config import Config
from daps_webui.utils import webui_utils
from daps_webui.utils.logger_utils import init_logger
from daps_webui.utils.webui_utils import get_instances
from DapsEX.border_replacerr import BorderReplacerr
from DapsEX.plex_upload import PlexUploaderr
from DapsEX.poster_renamerr import PosterRenamerr
from DapsEX.unmatched_assets import UnmatchedAssets
from progress import progress_instance

# all globals needs to be defined here
global_config = Config()
db = SQLAlchemy()
migrate = Migrate()
progress_dict = {}
executor = ThreadPoolExecutor(max_workers=2)

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
    migrate.init_app(app, db)
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
        daps_logger.debug("Poster Renamerr Payload:")
        daps_logger.debug(pformat(poster_renamer_payload))
        daps_logger.debug(
            f"Unmatched assets flag: {poster_renamer_payload.unmatched_assets}"
        )
        daps_logger.debug(
            f"Only unmatched flag: {poster_renamer_payload.only_unmatched}"
        )

        job_id = progress_instance.add_job()
        daps_logger.info(f"Job Poster Renamerr: '{job_id}' added.")

        renamer = PosterRenamerr(poster_renamer_payload)

        if webhook_item:
            daps_logger.debug("Submitting webhook task to thread pool")
            future = executor.submit(
                renamer.run,
                progress_instance,
                job_id,
                webhook_item,
            )
            daps_logger.debug("Task submitted successfully")
        else:
            if (
                poster_renamer_payload.unmatched_assets
                and poster_renamer_payload.only_unmatched
            ):
                daps_logger.debug("Running unmatched assets task first...")
                unmatched_assets_future = executor.submit(
                    handle_unmatched_assets_task, radarr, sonarr, plex
                )
                unmatched_assets_future.result()

            daps_logger.debug("Submitting renamer task to thread pool")
            future = executor.submit(renamer.run, progress_instance, job_id)
            daps_logger.debug("Task submitted successfully")

        def remove_job_cb(fut):
            sleep(2)
            progress_instance.remove_job(job_id)
            daps_logger.info(f"Poster Renamerr Job: {job_id} has been removed")

        def run_unmatched_assets_callback(fut):
            handle_unmatched_assets_task(radarr, sonarr, plex)

        def run_plex_upload_callback(fut):
            try:
                media_dict = fut.result()
                daps_logger.debug(f"Media dict from renamer: {media_dict}")
                handle_plex_uploaderr_task(
                    plex, radarr, sonarr, webhook_item, media_dict
                )
            except Exception as e:
                daps_logger.error(f"Error in Plex Upload Callback: {e}")

        if poster_renamer_payload.upload_to_plex:
            daps_logger.debug("Upload to plex flag is true, setting up callback...")

            future.add_done_callback(run_plex_upload_callback)

        if poster_renamer_payload.unmatched_assets:
            daps_logger.debug("Unmatched assets flag is true, setting up callback...")

            future.add_done_callback(run_unmatched_assets_callback)

        future.add_done_callback(remove_job_cb)

        return {
            "message": "Poster renamer task started",
            "job_id": job_id,
            "success": True,
        }
    except Exception as e:
        daps_logger.error(f"Error in Poster Renamer Task: {str(e)}")
        return {"success": False, "message": str(e)}


def run_border_replacer_task():
    try:
        border_replacerr_payload = webui_utils.create_border_replacer_payload()

        daps_logger.debug("Border Replacerr Payload:")
        daps_logger.debug(pformat(border_replacerr_payload))

        job_id = progress_instance.add_job()
        daps_logger.debug(f"Job Border Replacerr: '{job_id}' added.")

        border_replacerr = BorderReplacerr(
            custom_color=None, payload=border_replacerr_payload
        )
        daps_logger.debug("Submitting border replacerr task to thread pool")
        future = executor.submit(
            border_replacerr.replace_current_assets, progress_instance, job_id
        )
        daps_logger.debug("Task submitted successfully")

        def remove_job_cb(fut):
            sleep(2)
            progress_instance.remove_job(job_id)
            daps_logger.info(f"Border Replacer Job: {job_id} has been removed")

        future.add_done_callback(remove_job_cb)

        return {
            "message": "Border replacer task started",
            "job_id": job_id,
            "success": True,
        }
    except Exception as e:
        daps_logger.error(f"Error in Border Replacer Task: {str(e)}")
        return {"success": False, "message": str(e)}


def handle_unmatched_assets_task(radarr, sonarr, plex):
    try:
        with app.app_context():
            unmatched_assets_payload = webui_utils.create_unmatched_assets_payload(
                radarr, sonarr, plex
            )
            daps_logger.debug("Unmatched Assets Payload:")
            daps_logger.debug(pformat(unmatched_assets_payload))
            job_id = progress_instance.add_job()
            daps_logger.info(f"Job Unmatched Assets: '{job_id}' added.")

            unmatched_assets = UnmatchedAssets(unmatched_assets_payload)
            daps_logger.debug("Submitting unmatched assets task to thread pool")
            future = executor.submit(
                unmatched_assets.run,
                progress_instance,
                job_id,
            )
            daps_logger.debug("Task submitted successfully")

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


def handle_plex_uploaderr_task(
    plex,
    radarr,
    sonarr,
    webhook_item: dict | None = None,
    media_dict: dict | None = None,
):
    with app.app_context():
        plex_uploader_payload = webui_utils.create_plex_uploader_payload(
            radarr, sonarr, plex
        )
        daps_logger.debug("Plex Uploaderr Payload:")
        daps_logger.debug(pformat(plex_uploader_payload))

        job_id = progress_instance.add_job()
        daps_logger.info(f"Job Plex Uploaderr: '{job_id}' added.")
        if webhook_item and media_dict:
            plex_uploaderr = PlexUploaderr(
                plex_uploader_payload,
                webhook_item=webhook_item,
                media_dict=media_dict,
            )

            daps_logger.debug("Submitting webhook plex uploaderr task to thread pool")
            future = executor.submit(
                plex_uploaderr.upload_posters_webhook,
            )
            daps_logger.debug("Task submitted successfully")
        else:
            plex_uploaderr = PlexUploaderr(plex_uploader_payload)

            daps_logger.debug("Submitting plex uploaderr task to thread pool")
            future = executor.submit(
                plex_uploaderr.upload_posters_full,
                progress_instance,
                job_id,
            )
            daps_logger.debug("Task submitted successfully")

        def remove_job_cb(fut):
            sleep(2)
            progress_instance.remove_job(job_id)
            daps_logger.info(f"Plex uploaderr: {job_id} has been removed")

        future.add_done_callback(remove_job_cb)
        return {
            "message": "Plex uploaderr task started",
            "job_id": job_id,
            "success": True,
        }


def run_unmatched_assets_task():
    from daps_webui.models import PlexInstance, RadarrInstance, SonarrInstance

    try:
        radarr = get_instances(RadarrInstance())
        sonarr = get_instances(SonarrInstance())
        plex = get_instances(PlexInstance())

        return handle_unmatched_assets_task(radarr, sonarr, plex)
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_plex_uploaderr_task():
    from daps_webui.models import PlexInstance, RadarrInstance, SonarrInstance

    try:
        radarr = get_instances(RadarrInstance())
        sonarr = get_instances(SonarrInstance())
        plex = get_instances(PlexInstance())

        return handle_plex_uploaderr_task(plex, radarr, sonarr)
    except Exception as e:
        return {"success": False, "message": str(e)}


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
