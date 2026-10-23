"""Tag lookups shared by the web API, Streamlit, the scraper API and scripts."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.extraction import EmailRecord
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.models.tag import Tag


class TagNotAllowed(ValueError):
    pass


def list_tags(db: Session, active_only: bool = False) -> list[Tag]:
    stmt = select(Tag).order_by(Tag.id)
    if active_only:
        stmt = stmt.where(Tag.is_active.is_(True))
    return list(db.scalars(stmt).all())


def active_tag_names(db: Session) -> list[str]:
    return [t.name for t in list_tags(db, active_only=True)]


def get_tag(db: Session, name: str) -> Optional[Tag]:
    return db.scalar(select(Tag).where(Tag.name == name))


def check_tag(db: Session, name: str, current: Optional[str] = None) -> str:
    """Validates a tag chosen for a job or candidate.

    New choices must be active; keeping the record's current tag is allowed even if that
    tag has since been deactivated.
    """
    tag = get_tag(db, name)
    if tag and (tag.is_active or name == current):
        return name
    raise TagNotAllowed(f"Unknown or inactive tag '{name}'. Choose one of: {', '.join(active_tag_names(db))}")


def tag_usage(db: Session) -> dict[str, dict[str, int]]:
    """Per tag name: how many jobs, candidates and email records use it."""
    usage: dict[str, dict[str, int]] = {}
    for key, model in (("jobs", Job), ("candidates", Candidate), ("email_records", EmailRecord)):
        for name, count in db.execute(select(model.tag, func.count()).group_by(model.tag)):
            usage.setdefault(name, {"jobs": 0, "candidates": 0, "email_records": 0})[key] = count
    return usage


async def async_active_tag_names(db: AsyncSession) -> list[str]:
    result = await db.scalars(select(Tag.name).where(Tag.is_active.is_(True)).order_by(Tag.id))
    return list(result.all())
