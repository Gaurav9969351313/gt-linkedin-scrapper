import asyncio
import logging
import uvicorn
import prefect
from prefect.server.api.server import create_app
from threading import Thread

logger = logging.getLogger(__name__)


def run_prefect_server():
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=4200, log_level="info")


def run_api():
    uvicorn.run("gt_linkedin_scraper.api.main:app", host="0.0.0.0", port=8000, reload=True)


def run_worker():
    import subprocess
    subprocess.run(["prefect", "worker", "start", "--pool", "default"])


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting dev runner")

    server_thread = Thread(target=run_prefect_server, daemon=True)
    server_thread.start()

    import time
    time.sleep(5)

    worker_thread = Thread(target=run_worker, daemon=True)
    worker_thread.start()

    run_api()


if __name__ == "__main__":
    main()
