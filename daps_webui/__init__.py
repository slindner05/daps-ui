import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

from daps_webui.config.config import Config
from daps_webui.utils import webui_utils
from daps_webui.utils.logger_utils import init_logger
from daps_webui.utils.webui_utils import get_instances
from DapsEX.poster_renamerr import PosterRenamerr
from DapsEX.unmatched_assets import UnmatchedAssets
from DapsEX.utils import construct_schedule_time, parse_schedule_string
from progress import progress_instance

# all globals needs to be defined here
global_config = Config()
db = SQLAlchemy()
progress_dict = {}
executor = ThreadPoolExecutor(max_workers=2)
scheduler = BackgroundScheduler()
scheduler.start()

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

    # import needed blueprints
    from daps_webui.views.home.home import home
    from daps_webui.views.poster_renamer.poster_renamer import poster_renamer
    from daps_webui.views.settings.settings import settings

    # register blueprints
    app.register_blueprint(home)
    app.register_blueprint(settings)
    app.register_blueprint(poster_renamer)

    return app


app = create_app()
daps_logger.info("Created app")


def initialize_database():
    db.create_all()


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


def schedule_jobs():
    from daps_webui.models import Settings

    settings = Settings.query.first()

    def add_job_safe(func, job_id, schedule, schedule_name):
        if not schedule:
            daps_logger.warning(f"No schedule found for {schedule_name}. Skipping..")
            return

        try:
            parsed_schedule = parse_schedule_string(schedule, daps_logger)
            for i, parsed_schedule in enumerate(parsed_schedule):
                schedule_time = construct_schedule_time(parsed_schedule)
                unique_job_id = f"{job_id}_{i}"
                scheduler.add_job(
                    func,
                    "cron",
                    **parsed_schedule,
                    id=unique_job_id,
                    replace_existing=True,
                )
                daps_logger.info(f"Scheduled job: '{job_id}' {schedule_time}")
        except ValueError as e:
            daps_logger.error(
                f"Failed to schedule job '{job_id}' for {schedule_name}: {e}"
            )

    job_configs = {
        "run_renamerr": {
            "schedule": (
                getattr(settings, "poster_renamer_schedule", None) if settings else None
            ),
            "function": run_renamer_scheduled,
            "name": "poster_renamerr",
        },
        "run_unmatched_assets": {
            "schedule": (
                getattr(settings, "unmatched_assets_schedule", None)
                if settings
                else None
            ),
            "function": run_unmatched_scheduled,
            "name": "unmatched_assets",
        },
    }
    for job_id, job_config in job_configs.items():
        add_job_safe(
            job_config["function"], job_id, job_config["schedule"], job_config["name"]
        )


def run_renamer_scheduled():
    with app.app_context():
        result = run_renamer_task()
        if result["success"] is False:
            daps_logger.error(
                f"Error running scheduled renamer job: {result['message']}"
            )
        else:
            daps_logger.info(
                f"Scheduled renamer job started successfully with job_id: {result['job_id']}"
            )


def run_unmatched_scheduled():
    with app.app_context():
        result = run_unmatched_assets_task()
        if result["success"] is False:
            daps_logger.error(
                f"Error running scheduled unmatched assets job: {result['message']}"
            )
        else:
            daps_logger.info(
                f"Scheduled unmatched assets job started successfully with job_id: {result['job_id']}"
            )


with app.app_context():
    initialize_database()
    schedule_jobs()


@app.route("/arr-webhook", methods=["POST"])
def recieve_webhook():
    from daps_webui.models import Settings

    run_single_item = Settings.query.with_entities(Settings.run_single_item).scalar()
    if run_single_item is None:
        daps_logger.error("No settings found or run_single_item is not configured.")
        return "Settings not configured", 500
    if not run_single_item:
        daps_logger.debug("Single item processing is disabled in settings.")
        return "Single item processing disabled", 403

    data = request.json
    if not data:
        daps_logger.error("No data recieved in the webhook")
        return "No data recieved", 400
    daps_logger.debug(f"===== Webhook data =====\n{data}")

    valid_event_types = ["Download", "Grab", "MovieAdded", "SeriesAdd", "Import"]
    webhook_event_type = data.get("eventType", "")

    if webhook_event_type == "Test":
        daps_logger.info("Test event recived successfully")
        return "OK", 200

    if webhook_event_type not in valid_event_types:
        daps_logger.debug(f"'{webhook_event_type}' is not a valid event type")
        return "Invalid event type", 400

    daps_logger.info(f"Processing event type: {webhook_event_type}")
    try:
        item_type = (
            "movie" if "movie" in data else "series" if "series" in data else None
        )
        if not item_type:
            daps_logger.error("Neither 'movie' nor 'series' found in webhook data")
            return "Invalid webhook data", 400
        id = data.get(item_type, {}).get("id", None)
        id = int(id)
        if not id:
            daps_logger.error(f"Item ID not found for {item_type} in webhook data")
            return "Invalid webhook data", 400
        instance = data.get("instanceName", "").lower()
        if not instance:
            daps_logger.error(
                "Instance name missing from webhook data, please configure in arr settings."
            )
            return "Invalid webhook data", 400
        new_item = {"type": item_type, "item_id": id, "instance_name": instance}
        daps_logger.debug(f"Extracted item: {new_item}")
        run_renamer_task(webhook_item=new_item)

    except Exception as e:
        daps_logger.error(
            f"Error retrieving single item from webhook: {e}", exc_info=True
        )
        return "Internal server error", 500

    return "OK", 200


@app.route("/run-unmatched-job", methods=["POST"])
def run_unmatched():
    result = run_unmatched_assets_task()
    if result["success"] is False:
        return jsonify(result), 500
    return jsonify(result), 202


@app.route("/run-renamer-job", methods=["POST"])
def run_renamer():
    result = run_renamer_task()
    if result["success"] is False:
        return jsonify(result), 500
    return jsonify(result), 202


@app.route("/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    job_progress = progress_instance.get_progress(job_id)
    if job_progress:
        value, state = job_progress
        return jsonify({"job_id": job_id, "state": state, "value": value})
    else:
        return jsonify({"error": "Job not found"}), 404
