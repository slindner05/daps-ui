import logging

from apscheduler.schedulers.background import BackgroundScheduler

from daps_webui.config.config import Config
from daps_webui.utils.logger_utils import init_logger

global_config = Config()
scheduler = BackgroundScheduler()

daps_logger = logging.getLogger("daps-web")
log_level_str = getattr(global_config, "MAIN_LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str, logging.INFO)
init_logger(daps_logger, global_config.logs / "web-ui", "web_ui", log_level)


def on_starting(server):
    from daps_webui import app
    from daps_webui.utils.scheduler import schedule_jobs

    with app.app_context():
        schedule_jobs(scheduler)
        scheduler.start()
        daps_logger.info("Scheduler started in master process")


def post_fork(server, worker):
    daps_logger.handlers.clear()
    init_logger(daps_logger, global_config.logs / "web-ui", "web_ui", log_level)
    daps_logger.info(f"Worker {worker.pid} started.")


def on_exit(server):
    if scheduler.running:
        scheduler.shutdown()
