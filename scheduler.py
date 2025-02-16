import os
import socket

from apscheduler.schedulers.background import BackgroundScheduler

from daps_webui import (
    daps_logger,
    run_drive_sync_task,
    run_plex_uploaderr_task,
    run_renamer_task,
    run_unmatched_assets_task,
)
from daps_webui.utils.database import Database
from DapsEX.settings import Settings
from DapsEX.utils import construct_schedule_time, parse_schedule_string


def start_scheduler(scheduler):
    from daps_webui import app

    with app.app_context():
        schedule_jobs(scheduler)

    scheduler.start()
    daps_logger.info("Scheduler started.")

    with app.app_context():
        update_jobs_db(scheduler)


def reload_jobs_worker(scheduler):
    from daps_webui import app

    socket_path = Settings.SOCKET_PATH.value
    if os.path.exists(socket_path):
        os.remove(socket_path)
    daps_logger.info(f"Starting reload socket server at {socket_path}")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    os.chmod(socket_path, 0o777)
    server.listen(5)
    while True:
        daps_logger.info("Waiting for reload signal...")
        conn, _ = server.accept()
        with conn:
            data = conn.recv(1024).decode()
            if data.strip() == "reload":
                daps_logger.info("Reload signal received. Reloading jobs...")
                with app.app_context():
                    schedule_jobs(scheduler)
                    update_jobs_db(scheduler)
                daps_logger.info("Jobs reloaded successfully")


def update_jobs_db(scheduler):
    from daps_webui import db

    db_instance = Database(db, daps_logger)
    jobs = scheduler.get_jobs()
    excluded_jobs = {"reload_jobs"}
    job_groups = {}

    for job in jobs:
        job_id = job.id
        next_run = job.next_run_time

        if job_id in excluded_jobs:
            daps_logger.debug(f"Skipping job: {job_id}")
            continue

        base_job_name = "_".join(job_id.split("_")[:-1])

        if base_job_name not in job_groups or (
            next_run and next_run < job_groups[base_job_name]
        ):
            job_groups[base_job_name] = next_run

    for base_job_name, next_run in job_groups.items():
        db_instance.update_scheduled_job(base_job_name, next_run)
        daps_logger.debug(f"Updated Job: {base_job_name} next run time: {next_run}")


def schedule_jobs(scheduler: BackgroundScheduler):
    from daps_webui import app, db
    from daps_webui.models import Settings

    db_instance = Database(db, daps_logger)

    settings = Settings.query.first()

    def add_job_safe(func, job_id, schedule, schedule_name):
        if not schedule:
            daps_logger.warning(f"No schedule found for {schedule_name}. Skipping..")
            removed_jobs = []
            for job in scheduler.get_jobs():
                if job.id.startswith(job_id):
                    daps_logger.info(f"Removing obsolete job: {job.id}")
                    scheduler.remove_job(job.id)
                    removed_jobs.append(job.id)

            if removed_jobs:
                with app.app_context():
                    db_instance.clear_scheduled_job(job_id)
            return

        try:
            parsed_schedule = parse_schedule_string(schedule, daps_logger)
            for i, parsed_schedule_entry in enumerate(parsed_schedule):
                schedule_time = construct_schedule_time(parsed_schedule_entry)
                unique_job_id = f"{job_id}_{i}"
                scheduler.add_job(
                    func,
                    "cron",
                    **parsed_schedule_entry,
                    id=unique_job_id,
                    replace_existing=True,
                    misfire_grace_time=60,
                    args=(scheduler,),
                )
                daps_logger.info(f"Scheduled job: '{unique_job_id}' {schedule_time}")

        except ValueError as e:
            daps_logger.error(
                f"Failed to schedule job '{job_id}' for {schedule_name}: {e}"
            )

    job_configs = {
        "poster_renamerr": {
            "schedule": (
                getattr(settings, "poster_renamer_schedule", None) if settings else None
            ),
            "function": run_renamer_scheduled,
            "name": "poster_renamerr",
        },
        "unmatched_assets": {
            "schedule": (
                getattr(settings, "unmatched_assets_schedule", None)
                if settings
                else None
            ),
            "function": run_unmatched_scheduled,
            "name": "unmatched_assets",
        },
        "plex_uploaderr": {
            "schedule": (
                getattr(settings, "plex_uploaderr_schedule", None) if settings else None
            ),
            "function": run_plex_upload_scheduled,
            "name": "plex_uploaderr",
        },
        "drive_sync": {
            "schedule": (
                getattr(settings, "drive_sync_schedule", None) if settings else None
            ),
            "function": run_drive_sync_scheduled,
            "name": "drive_sync",
        },
    }

    for job_id, job_config in job_configs.items():
        add_job_safe(
            job_config["function"],
            job_id,
            job_config["schedule"],
            job_config["name"],
        )


def run_renamer_scheduled(scheduler):
    from daps_webui import app, db

    database_instance = Database(db, daps_logger)

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled renamerr job")
            result = run_renamer_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled renamer job: {result['message']}"
                )
                database_instance.add_job_to_history(
                    Settings.POSTER_RENAMERR.value, "failed", "scheduled"
                )
                update_jobs_db(scheduler)
            else:
                daps_logger.info(
                    f"Scheduled renamer job started successfully with job_id: {result['job_id']}"
                )
                database_instance.add_job_to_history(
                    Settings.POSTER_RENAMERR.value, "success", "scheduled"
                )
                update_jobs_db(scheduler)
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled renamerr job: {e}")
        database_instance.add_job_to_history(
            Settings.POSTER_RENAMERR.value, "failed", "scheduled"
        )
        update_jobs_db(scheduler)


def run_unmatched_scheduled(scheduler):
    from daps_webui import app, db

    database_instance = Database(db, daps_logger)
    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled unmatched assets job")
            result = run_unmatched_assets_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled unmatched assets job: {result['message']}"
                )
                database_instance.add_job_to_history(
                    Settings.UNMATCHED_ASSETS.value, "failed", "scheduled"
                )
                update_jobs_db(scheduler)
            else:
                daps_logger.info(
                    f"Scheduled unmatched assets job started successfully with job_id: {result['job_id']}"
                )
                database_instance.add_job_to_history(
                    Settings.UNMATCHED_ASSETS.value, "success", "scheduled"
                )
                update_jobs_db(scheduler)
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled unmatched assets job: {e}")
        database_instance.add_job_to_history(
            Settings.UNMATCHED_ASSETS.value, "failed", "scheduled"
        )
        update_jobs_db(scheduler)


def run_plex_upload_scheduled(scheduler):
    from daps_webui import app, db

    database_instance = Database(db, daps_logger)

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled plex uploaderr job")
            result = run_plex_uploaderr_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled plex uploaderr job: {result['message']}"
                )
                database_instance.add_job_to_history(
                    Settings.PLEX_UPLOADERR.value, "failed", "scheduled"
                )
                update_jobs_db(scheduler)
            else:
                daps_logger.info(
                    f"Scheduled plex uploaderr job started successfully with job_id: {result['job_id']}"
                )
                database_instance.add_job_to_history(
                    Settings.PLEX_UPLOADERR.value, "success", "scheduled"
                )
                update_jobs_db(scheduler)
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled plex uploaderr job: {e}")
        database_instance.add_job_to_history(
            Settings.PLEX_UPLOADERR.value, "failed", "scheduled"
        )
        update_jobs_db(scheduler)


def run_drive_sync_scheduled(scheduler):
    from daps_webui import app, db

    database_instance = Database(db, daps_logger)

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled drive sync job")
            result = run_drive_sync_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled drive sync job: {result['message']}"
                )
                database_instance.add_job_to_history(
                    Settings.DRIVE_SYNC.value, "failed", "scheduled"
                )
                update_jobs_db(scheduler)
            else:
                daps_logger.info(
                    f"Scheduled drive sync job started successfully with job_id: {result['job_id']}"
                )
                database_instance.add_job_to_history(
                    Settings.DRIVE_SYNC.value, "success", "scheduled"
                )
                update_jobs_db(scheduler)
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled drive sync job: {e}")
        database_instance.add_job_to_history(
            Settings.DRIVE_SYNC.value, "failed", "scheduled"
        )
        update_jobs_db(scheduler)


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    start_scheduler(scheduler)

    reload_jobs_worker(scheduler)
