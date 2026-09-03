import asyncio
import logging
import yaml
from pathlib import Path
from sqlalchemy import create_engine, text

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.models.enums import JobStatus, Tag

logger = logging.getLogger(__name__)


def sync_create_tables():
    url = settings.database_url
    sync_url = url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    from gt_linkedin_scraper.core.database import Base
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified")


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
        for jd in jobs:
            tag = jd.get("tag", "java")
            try:
                tag_enum = Tag(tag)
            except ValueError:
                tag_enum = Tag.JAVA

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
                "tag": tag_enum.value,
                "cron": jd.get("cron", ""),
                "status": JobStatus.IDLE.value,
            })
        conn.commit()
    logger.info(f"Seeded {len(jobs)} jobs")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_create_tables()
    sync_seed_jobs()
