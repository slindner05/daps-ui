from daps_webui import (app, daps_logger, run_renamer_task,
                        run_unmatched_assets_task)
from DapsEX.utils import construct_schedule_time, parse_schedule_string


def schedule_jobs(scheduler):
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
