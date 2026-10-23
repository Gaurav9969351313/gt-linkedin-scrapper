"""Load jobs from config/jobs.yaml, overwriting jobs with the same id. Run scripts/migrate.py first.

Jobs are normally managed in the web app (Scraper jobs). The scraper API only seeds
from config/jobs.yaml when the jobs table is empty; use this script to force a reload.
"""
import logging
import yaml
from pathlib import Path
from sqlalchemy import create_engine, text

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.models.enums import JobStatus

logger = logging.getLogger(__name__)


def sync_seed_jobs():
    config_path = Path(settings.jobs_config_path)
    if not config_path.exists():
        logger.error("Jobs config not found", extra={"path": str(config_path)})
        return

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    jobs = data.get("jobs", [])
    if not jobs:
        logger.info("No jobs found in config")
        return

    url = settings.database_url
    sync_url = url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        tags = {row[0] for row in conn.execute(text("SELECT name FROM tags WHERE is_active"))}
        for jd in jobs:
            tag = jd.get("tag", "java")
            if tag not in tags:
                logger.warning(f"Skipping job {jd['id']}: unknown or inactive tag '{tag}'")
                continue

            stmt = text("""
                INSERT INTO jobs (id, keyword, scroll_count, tag, cron_expression, status)
                VALUES (:id, :keyword, :scroll_count, :tag, :cron, :status)
                ON CONFLICT (id) DO UPDATE SET
                    keyword = EXCLUDED.keyword,
                    scroll_count = EXCLUDED.scroll_count,
                    tag = EXCLUDED.tag,
                    cron_expression = EXCLUDED.cron_expression
            """)
            conn.execute(stmt, {
                "id": jd["id"],
                "keyword": jd["keyword"],
                "scroll_count": jd.get("scroll_count", 10),
                "tag": tag,
                "cron": jd.get("cron", ""),
                "status": JobStatus.IDLE.value,
            })
        # Explicit ids leave the id sequence behind; move it past them.
        conn.execute(text("SELECT setval(pg_get_serial_sequence('jobs', 'id'), COALESCE((SELECT MAX(id) FROM jobs), 0) + 1, false)"))
        conn.commit()
    logger.info(f"Seeded {len(jobs)} jobs")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_seed_jobs()
