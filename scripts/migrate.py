"""Bring the database schema up to date. Safe to run on every start.

    python scripts/migrate.py

- Database already managed by Alembic -> `alembic upgrade head`.
- Empty database -> create every table from the models and record the head revision,
  in one transaction (equivalent to create_all + `alembic stamp head`, but all-or-nothing).
  (The early migrations assume tables created by the original create_all(), so they
  cannot build a database from scratch.)
"""
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

import gt_linkedin_scraper.models  # noqa: F401  registers every table on Base.metadata
from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.database import Base
from gt_linkedin_scraper.models.tag import DEFAULT_TAGS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("migrate")


def main() -> int:
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)
    try:
        tables = set(inspect(engine).get_table_names())
        if "alembic_version" in tables:
            logger.info("Applying migrations (alembic upgrade head)")
            command.upgrade(alembic_cfg, "head")
        elif not tables:
            head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
            logger.info("Empty database: creating schema at revision %s", head)
            with engine.begin() as conn:
                Base.metadata.create_all(conn)
                conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
                conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})
                conn.execute(
                    text("INSERT INTO tags (name, label) VALUES (:name, :label)"),
                    [{"name": n, "label": label} for n, label in DEFAULT_TAGS],
                )
        else:
            logger.error(
                "Database has tables but no alembic_version. Check the schema matches the models, "
                "then run `alembic stamp head` once."
            )
            return 1
    finally:
        engine.dispose()
    logger.info("Database schema is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
