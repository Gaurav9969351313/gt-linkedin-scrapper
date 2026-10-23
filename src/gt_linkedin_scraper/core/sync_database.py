"""Synchronous SQLAlchemy session, for the Streamlit app, the web API and CLI scripts.

The scraper itself (API, Prefect flows) uses the async engine in core.database.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from gt_linkedin_scraper.core.config import settings

engine = create_engine(settings.database_url_sync, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
