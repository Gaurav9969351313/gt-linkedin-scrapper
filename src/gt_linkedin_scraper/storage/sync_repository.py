"""Synchronous queries for candidates, email stats and scrape jobs (Streamlit app, web API, scripts).

The async repositories for the scraper live in storage.repository.
"""
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.extraction import EmailRecord
from gt_linkedin_scraper.models.job import Job, RunLog


def get_candidates(db: Session, tag: Optional[str] = None) -> List[Candidate]:
    stmt = select(Candidate)
    if tag:
        stmt = stmt.where(Candidate.tag == tag)
    stmt = stmt.order_by(Candidate.created_at.desc())
    return list(db.scalars(stmt).all())


def get_candidate(db: Session, candidate_id: int) -> Optional[Candidate]:
    return db.get(Candidate, candidate_id)


def get_candidate_by_owner(db: Session, owner_id: int) -> Optional[Candidate]:
    return db.scalar(select(Candidate).where(Candidate.owner_id == owner_id).order_by(Candidate.id))


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
    existing.email_subject = candidate.email_subject
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
    total = db.scalar(select(func.count(EmailRecord.id)))
    tag_count = db.scalar(select(func.count(func.distinct(EmailRecord.tag))))

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


# ---------- scrape jobs ----------

def get_jobs(db: Session) -> List[Job]:
    return list(db.scalars(select(Job).order_by(Job.id)).all())


def get_job(db: Session, job_id: int) -> Optional[Job]:
    return db.get(Job, job_id)


def save_job(db: Session, job: Job) -> Job:
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: int) -> bool:
    """Deletes the job, its run logs and (via ON DELETE CASCADE) its email and post records."""
    job = db.get(Job, job_id)
    if not job:
        return False
    db.execute(delete(RunLog).where(RunLog.job_id == job_id))
    db.delete(job)
    db.commit()
    return True


def get_run_logs(db: Session, job_id: int, limit: int = 50) -> List[RunLog]:
    stmt = select(RunLog).where(RunLog.job_id == job_id).order_by(RunLog.started_at.desc(), RunLog.id.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def latest_run_logs(db: Session) -> dict[int, RunLog]:
    """Most recent run log per job id."""
    latest = (
        select(RunLog.job_id, func.max(RunLog.id).label("id")).group_by(RunLog.job_id).subquery()
    )
    rows = db.scalars(select(RunLog).join(latest, RunLog.id == latest.c.id)).all()
    return {r.job_id: r for r in rows}


def email_counts_by_job(db: Session) -> dict[int, int]:
    rows = db.execute(select(EmailRecord.job_id, func.count(EmailRecord.id)).group_by(EmailRecord.job_id)).all()
    return dict(rows)
