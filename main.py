import logging
import os
from logging import Logger
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from DapsEX import PosterRenamerr, UnmatchedAssets, YamlConfig
from DapsEX.logger import init_logger
from DapsEX.settings import Settings
from DapsEX.utils import construct_schedule_time, parse_schedule_string

log_level_env = os.getenv("MAIN_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_env, logging.INFO)
log_dir = Path(Settings.LOG_DIR.value) / Settings.MAIN.value
logger = logging.getLogger("Main")
init_logger(logger, log_dir, "main", log_level=log_level)
logger.info(f"LOG LEVEL: {log_level_env}")


def get_config(logger: Logger):
    config = YamlConfig(logger)
    logger.info("Yaml config initialized")
    return config


def run_renamer(config: YamlConfig):
    payload = config.create_poster_renamer_payload()
    renamerr = PosterRenamerr(
        payload.target_path,
        payload.source_dirs,
        payload.asset_folders,
        payload.border_replacerr,
        payload.log_level,
    )
    if payload.unmatched_assets:
        logger.info("Running poster renamerr + unmatched assets")
    else:
        logger.info("Running poster renamerr")
    renamerr.run(payload)
    logger.info("Finished poster renamerr")
    if payload.unmatched_assets:
        run_unmatched_assets(config)


def run_unmatched_assets(config: YamlConfig):
    payload = config.create_unmatched_assets_payload()
    unmatched_assets = UnmatchedAssets(
        payload.target_path, payload.asset_folders, payload.log_level
    )
    logger.info("Running unmatched assets")
    unmatched_assets.run(payload)
    logger.info("Finished unmatched assets")


def add_scheduled_jobs(scheduler: BackgroundScheduler, config: YamlConfig):
    def add_job_safe(func, job_id, schedule, schedule_name):

        if not schedule:
            logger.warning(f"No schedule found for {schedule_name}. Skipping Job")
            return
        try:
            parsed_schedules = parse_schedule_string(schedule, logger)
            for i, parsed_schedule in enumerate(parsed_schedules):
                schedule_time = construct_schedule_time(parsed_schedule)

                unique_job_id = f"{job_id}_{i}"
                scheduler.add_job(
                    func,
                    "cron",
                    **parsed_schedule,
                    args=[config],
                    id=unique_job_id,
                    replace_existing=True,
                )
                logger.info(f"Scheduled job '{job_id}' {schedule_time}")
        except ValueError as e:
            logger.error(f"Failed to schedule job '{job_id}' for {schedule_name}: {e}")

    job_configs = {
        "run_renamer": {
            "schedule": config.schedule_config.get(Settings.POSTER_RENAMERR.value),
            "function": run_renamer,
            "name": Settings.POSTER_RENAMERR.value,
        },
        "run_unmatched_assets": {
            "schedule": config.schedule_config.get(Settings.UNMATCHED_ASSETS.value),
            "function": run_unmatched_assets,
            "name": Settings.UNMATCHED_ASSETS.value,
        },
    }

    for job_id, job_config in job_configs.items():
        add_job_safe(
            job_config["function"],
            job_id,
            job_config["schedule"],
            job_config["name"],
        )


def run_cli():
    config = get_config(logger)
    scheduler = BackgroundScheduler()
    add_scheduled_jobs(scheduler, config)
    scheduler.start()
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    run_cli()
    # run_unmatched_assets()
