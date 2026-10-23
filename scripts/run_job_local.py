import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ["PYTHONUNBUFFERED"] = "1"

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.scheduler.tasks import run_job

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("run_job_local")


async def main(job_id: int) -> None:
    session: AsyncSession = async_session_factory()
    try:
        print(f"[START] Running job {job_id} locally without Prefect", flush=True)
        logger.info("Starting job %s locally (no Prefect)", job_id)
        await run_job(job_id, session)
        print(f"[DONE] Job {job_id} finished", flush=True)
        logger.info("Job %s finished", job_id)
    finally:
        await session.close()


if __name__ == "__main__":
    job_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(job_id))
