import logging
from typing import List
from prefect import flow, task
from sqlalchemy.ext.asyncio import AsyncSession
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.storage.repository import JobRepository
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.scheduler.tasks import run_job

logger = logging.getLogger(__name__)


@task(retries=3, retry_delay_seconds=[60, 120, 300])
async def scrape_job_task(job_id: int) -> dict:
    async with async_session_factory() as db:
        try:
            await run_job(job_id, db)
            return {"job_id": job_id, "status": "completed"}
        except Exception as exc:
            logger.error("Task failed", extra={"job_id": job_id, "error": str(exc)})
            return {"job_id": job_id, "status": "error", "error": str(exc)}


@flow(name="scrape-single-job")
async def scrape_single_flow(job_id: int) -> dict:
    result = await scrape_job_task(job_id)
    return result


@flow(name="scrape-all-jobs")
async def scrape_all_flow() -> List[dict]:
    async with async_session_factory() as db:
        repo = JobRepository(db)
        jobs = await repo.get_all(limit=1000)
    results = []
    for job in jobs:
        if job.status.value == "hold":
            continue
        result = await scrape_job_task(job.id)
        results.append(result)
    return results
