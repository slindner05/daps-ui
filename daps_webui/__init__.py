from sqlalchemy import false
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from time import sleep
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from daps_webui.config.config import Config
from concurrent.futures import ThreadPoolExecutor
from DapsEX.poster_renamerr import PosterRenamerr
from daps_webui.utils import webui_utils
from daps_webui.utils.webui_utils import *
from progress import *

# all globals needs to be defined here
global_config = Config()
db = SQLAlchemy()
progress_dict = {}
executor = ThreadPoolExecutor(max_workers=2)
scheduler = BackgroundScheduler()
scheduler.start()

# define all loggers
daps_logger = logging.getLogger("daps")


def create_app() -> Flask:
    # init flask app
    app = Flask(__name__)
    app.config.from_object(global_config)

    # initiate logger(s)
    from daps_webui.utils.logger_utils import init_logger

    init_logger(daps_logger, global_config.logs, "daps_log.log", logging.INFO)

    # initiate database
    db.init_app(app)

    # import needed blueprints
    from daps_webui.views.home.home import home
    from daps_webui.views.settings.settings import settings
    from daps_webui.views.poster_renamer.poster_renamer import poster_renamer

    # register blueprints
    app.register_blueprint(home)
    app.register_blueprint(settings)
    app.register_blueprint(poster_renamer)

    return app


app = create_app()
with app.app_context():
    db.create_all()


def run_renamer_task():
    from daps_webui.models import RadarrInstance, SonarrInstance, PlexInstance

    try:
        radarr = get_instances(RadarrInstance())
        sonarr = get_instances(SonarrInstance())
        plex = get_instances(PlexInstance())
        payload = webui_utils.create_poster_renamer_payload(radarr, sonarr, plex)

        job_id = progress_instance.add_job()

        renamer = PosterRenamerr(
            payload.target_path, payload.source_dirs, payload.asset_folders
        )
        future = executor.submit(renamer.run, payload, progress_instance, job_id)

        def remove_job_cb(fut):
            sleep(2)
            progress_instance.remove_job(job_id)
            print(f"Job {job_id} has been removed", flush=True)

        future.add_done_callback(remove_job_cb)

        return {"message": "Poster renamer started", "job_id": job_id, "success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.route("/run-renamer-job", methods=["POST"])
def run_renamer():
    result = run_renamer_task()
    if result["success"] is False:
        return jsonify(result), 500
    return jsonify(result), 202


def run_renamer_scheduled():
    with app.app_context():
        result = run_renamer_task()
        if result["success"] is False:
            print(
                f"Error running scheduled renamer job: {result['message']}", flush=True
            )
        else:
            print(
                f"Scheduled renamer job started successfully with job_id: {result['job_id']}",
                flush=True,
            )

def schedule_poster_renamer():
    from daps_webui.models import Settings

    with app.app_context():
        settings = Settings.query.first()
        if settings and settings.poster_renamer_schedule:
            cron_schedule = settings.poster_renamer_schedule
            scheduler.remove_all_jobs()
            try:
                print(f"Scheduling job with cron: {cron_schedule}", flush=True)
                scheduler.add_job(
                    run_renamer_scheduled,
                    CronTrigger.from_crontab(cron_schedule),
                    id="poster_renamer_job",
                    replace_existing=True,
                )
                print(f"Cron job scheduled with {cron_schedule}", flush=True)
            except Exception as e:
                print(f"Error scheduling job: {e}", flush=True)


@app.route("/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    job_progress = progress_instance.get_progress(job_id)
    if job_progress:
        value, state = job_progress
        return jsonify({"job_id": job_id, "state": state, "value": value})
    else:
        return jsonify({"error": "Job not found"}), 404


with app.app_context():
    schedule_poster_renamer()
