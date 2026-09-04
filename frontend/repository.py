import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session

from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.extraction import EmailRecord


def get_candidates(db: Session, tag: Optional[str] = None) -> List[Candidate]:
    stmt = select(Candidate)
    if tag:
        stmt = stmt.where(Candidate.tag == tag)
    stmt = stmt.order_by(Candidate.created_at.desc())
    return list(db.scalars(stmt).all())


def get_candidate(db: Session, candidate_id: int) -> Optional[Candidate]:
    return db.get(Candidate, candidate_id)


def create_candidate(db: Session, candidate: Candidate) -> Candidate:
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def update_candidate(db: Session, candidate_id: int, candidate: Candidate) -> Optional[Candidate]:
    existing = db.get(Candidate, candidate_id)
    if not existing:
        return None
    existing.name = candidate.name
    existing.number = candidate.number
    existing.subscription = candidate.subscription
    existing.is_active = candidate.is_active
    existing.email = candidate.email
    existing.email_password = candidate.email_password
    existing.resume = candidate.resume
    existing.email_body = candidate.email_body
    existing.tag = candidate.tag
    db.commit()
    db.refresh(existing)
    return existing


def delete_candidate(db: Session, candidate_id: int) -> bool:
    existing = db.get(Candidate, candidate_id)
    if not existing:
        return False
    db.delete(existing)
    db.commit()
    return True


def get_email_stats(db: Session):
    total_stmt = select(func.count(EmailRecord.id))
    total = db.scalar(total_stmt)

    tag_count_stmt = select(func.count(func.distinct(EmailRecord.tag)))
    tag_count = db.scalar(tag_count_stmt)

    tag_stmt = (
        select(EmailRecord.tag, func.count(EmailRecord.id).label("count"))
        .group_by(EmailRecord.tag)
        .order_by(EmailRecord.tag)
    )
    tags = db.execute(tag_stmt).all()

    date_stmt = (
        select(func.date(EmailRecord.scraped_at).label("date"), func.count(EmailRecord.id).label("count"))
        .group_by(func.date(EmailRecord.scraped_at))
        .order_by(func.date(EmailRecord.scraped_at))
    )
    dates = db.execute(date_stmt).all()

    return total, tag_count, tags, dates
