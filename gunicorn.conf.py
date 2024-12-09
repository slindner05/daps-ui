import logging

from daps_webui import create_app, schedule_jobs, scheduler
from daps_webui.config.config import Config
from daps_webui.utils.logger_utils import init_logger

global_config = Config()


def post_fork(server, worker):

    app = create_app()
    daps_logger = logging.getLogger("daps-web")

    log_level_str = getattr(global_config, "MAIN_LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str, logging.INFO)
    init_logger(daps_logger, global_config.logs / "web-ui", "web_ui", log_level)

    daps_logger.info(f"Worker {worker.pid} started.")

    with app.app_context():
        schedule_jobs()
        if not scheduler.running:
            scheduler.start()
            daps_logger.info("Scheduler started in worker process.")
