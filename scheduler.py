import os

from apscheduler.schedulers.background import BlockingScheduler

from daps_webui import (
    daps_logger,
    run_drive_sync_task,
    run_plex_uploaderr_task,
    run_renamer_task,
    run_unmatched_assets_task,
)
from DapsEX.utils import construct_schedule_time, parse_schedule_string


def start_scheduler():
    from daps_webui import app

    scheduler = BlockingScheduler()

    with app.app_context():
        schedule_jobs(scheduler)

    scheduler.add_job(
        reload_jobs,
        "interval",
        seconds=5,
        kwargs={"scheduler": scheduler, "app": app},
        id="reload_jobs",
        max_instances=1,
        misfire_grace_time=10,
        coalesce=True,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        daps_logger.info("Scheduler stopped.")


def reload_jobs(scheduler, app):
    if os.path.exists("/tmp/reload_signal"):
        daps_logger.info("Reload signal detected. Reloading jobs..")
        with app.app_context():
            schedule_jobs(scheduler)
        os.remove("/tmp/reload_signal")


def schedule_jobs(scheduler):
    from daps_webui.models import Settings

    settings = Settings.query.first()

    def add_job_safe(func, job_id, schedule, schedule_name):
        if not schedule:
            daps_logger.warning(f"No schedule found for {schedule_name}. Skipping..")
            for job in scheduler.get_jobs():
                if job.id.startswith(job_id):
                    daps_logger.info(f"Removing obsolete job: {job.id}")
                    scheduler.remove_job(job.id)
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
                )
                daps_logger.info(f"Scheduled job: '{unique_job_id}' {schedule_time}")

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
        "run_plex_uploaderr": {
            "schedule": (
                getattr(settings, "plex_uploaderr_schedule", None) if settings else None
            ),
            "function": run_plex_upload_scheduled,
            "name": "plex_uploaderr",
        },
        "run_drive_sync": {
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


def run_renamer_scheduled():
    from daps_webui import app

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled renamerr job")
            result = run_renamer_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled renamer job: {result['message']}"
                )
            else:
                daps_logger.info(
                    f"Scheduled renamer job started successfully with job_id: {result['job_id']}"
                )
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled renamerr job: {e}")


def run_unmatched_scheduled():
    from daps_webui import app

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled unmatched assets job")
            result = run_unmatched_assets_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled unmatched assets job: {result['message']}"
                )
            else:
                daps_logger.info(
                    f"Scheduled unmatched assets job started successfully with job_id: {result['job_id']}"
                )
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled unmatched assets job: {e}")


def run_plex_upload_scheduled():
    from daps_webui import app

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled plex uploaderr job")
            result = run_plex_uploaderr_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled plex uploaderr job: {result['message']}"
                )
            else:
                daps_logger.info(
                    f"Scheduled plex uploaderr job started successfully with job_id: {result['job_id']}"
                )
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled plex uploaderr job: {e}")


def run_drive_sync_scheduled():
    from daps_webui import app

    try:
        with app.app_context():
            daps_logger.debug("Starting scheduled drive sync job")
            result = run_drive_sync_task()
            if result["success"] is False:
                daps_logger.error(
                    f"Error running scheduled drive sync job: {result['message']}"
                )
            else:
                daps_logger.info(
                    f"Scheduled drive sync job started successfully with job_id: {result['job_id']}"
                )
    except Exception as e:
        daps_logger.debug(f"Failed to run scheduled drive sync job: {e}")


if __name__ == "__main__":
    start_scheduler()
