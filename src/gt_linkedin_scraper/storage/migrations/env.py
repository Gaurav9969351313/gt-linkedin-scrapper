from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from gt_linkedin_scraper.core.database import Base
from gt_linkedin_scraper.models.job import Job, RunLog
from gt_linkedin_scraper.models.enums import JobStatus, Tag
import yaml
from pathlib import Path
from gt_linkedin_scraper.core.config import settings


def upgrade() -> None:
    url = settings.database_url
    sync_url = url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)

    Base.metadata.create_all(engine)
    print("Alembic-style migration: tables created/verified.")


def seed_jobs() -> None:
    from gt_linkedin_scraper.core.database import engine
    from sqlalchemy import text as sql_text

    config_path = Path(settings.jobs_config_path)
    if not config_path.exists():
        print(f"Jobs config not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    jobs = data.get("jobs", [])
    if not jobs:
        print("No jobs found in config.")
        return

    with engine.connect() as conn:
        for job_def in jobs:
            tag = job_def.get("tag", "java")
            try:
                tag_enum = Tag(tag)
            except ValueError:
                tag_enum = Tag.JAVA

            status = JobStatus.IDLE

            stmt = sql_text("""
                INSERT INTO jobs (keyword, scroll_count, tag, cron_expression, status)
                VALUES (:keyword, :scroll_count, :tag, :cron, :status)
                ON CONFLICT DO NOTHING
            """)
            conn.execute(stmt, {
                "keyword": job_def["keyword"],
                "scroll_count": job_def.get("scroll_count", 10),
                "tag": tag_enum.value,
                "cron": job_def.get("cron", ""),
                "status": status.value,
            })
        conn.commit()
    print(f"Seeded {len(jobs)} jobs into database.")


if __name__ == "__main__":
    upgrade()
    seed_jobs()
