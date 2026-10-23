"""Startup reconciliation, run by the scraper API.

The jobs table is the source of truth (super admins manage it in the web app).
config/jobs.yaml is only used to seed jobs into an empty database.
"""
import logging
from pathlib import Path

import yaml
from sqlalchemy import func, select, text

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.scheduler.deployments import sync_all
from gt_linkedin_scraper.storage.repository import JobRepository
from gt_linkedin_scraper.storage.tags import async_active_tag_names

logger = logging.getLogger(__name__)


async def _seed_from_yaml(db) -> None:
    config_path = Path(settings.jobs_config_path)
    if not config_path.exists():
        logger.warning("Jobs config not found", extra={"path": str(config_path)})
        return
    with open(config_path, encoding="utf-8") as f:
        job_defs = (yaml.safe_load(f) or {}).get("jobs", [])

    tags = set(await async_active_tag_names(db))
    for jd in job_defs:
        tag = jd.get("tag", "java")
        if tag not in tags:
            logger.warning("Skipping seed job with unknown tag", extra={"job_id": jd.get("id"), "tag": tag})
            continue
        db.add(
            Job(
                id=jd["id"],
                keyword=jd["keyword"],
                scroll_count=jd.get("scroll_count", 10),
                tag=tag,
                cron_expression=jd.get("cron", ""),
                status=JobStatus.IDLE,
            )
        )
    await db.flush()
    # Seeded rows use explicit ids; move the sequence past them.
    await db.execute(
        text("SELECT setval(pg_get_serial_sequence('jobs', 'id'), COALESCE((SELECT MAX(id) FROM jobs), 0) + 1, false)")
    )
    logger.info("Seeded jobs from config", extra={"count": len(job_defs)})


async def _reconcile() -> None:
    async with async_session_factory() as db:
        if not await db.scalar(select(func.count(Job.id))):
            await _seed_from_yaml(db)
            await db.commit()
        jobs = await JobRepository(db).get_all(limit=10_000)

    await sync_all(jobs)
    logger.info("Deployments reconciled", extra={"count": len(jobs)})


async def run_deployer() -> None:
    await _reconcile()
