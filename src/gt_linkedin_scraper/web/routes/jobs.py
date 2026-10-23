"""LinkedIn scrape job management (super admin only).

Every change is saved to the database first and then pushed to Prefect. If Prefect is
unreachable the change is kept and the response carries a `warning`; the scraper API
re-syncs all deployments from the database when it next starts.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.job import Job, RunLog
from gt_linkedin_scraper.scheduler import deployments
from gt_linkedin_scraper.storage.sync_repository import (
    delete_job,
    email_counts_by_job,
    get_job,
    get_jobs,
    get_run_logs,
    latest_run_logs,
    save_job,
)
from gt_linkedin_scraper.storage.tags import TagNotAllowed, check_tag
from gt_linkedin_scraper.web.security import require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/jobs", tags=["jobs"], dependencies=[Depends(require_super_admin)])

MAX_SCROLL_COUNT = 100
SYNC_WARNING = (
    "Saved, but the Prefect schedule could not be updated ({error}). "
    "It will be synced the next time the scraper API starts."
)


class JobBody(BaseModel):
    keyword: str
    scroll_count: int = 5
    tag: str
    cron_expression: str


# ---------- helpers ----------

def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def serialize_run(run: RunLog) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "records_count": run.records_count,
        "error_message": run.error_message,
    }


def serialize_job(job: Job, last_run: Optional[RunLog] = None, email_count: int = 0) -> dict:
    return {
        "id": job.id,
        "keyword": job.keyword,
        "scroll_count": job.scroll_count,
        "tag": job.tag,
        "cron_expression": job.cron_expression,
        "status": job.status,
        "on_hold": job.status == JobStatus.HOLD,
        "created_at": _iso(job.created_at),
        "updated_at": _iso(job.updated_at),
        "last_run": serialize_run(last_run) if last_run else None,
        "email_count": email_count,
    }


def serialize_one(db: Session, job: Job, warning: Optional[str] = None) -> dict:
    data = serialize_job(job, latest_run_logs(db).get(job.id), email_counts_by_job(db).get(job.id, 0))
    data["warning"] = warning
    return data


def push_to_prefect(coro) -> Optional[str]:
    """Runs a Prefect sync coroutine; returns a warning instead of failing the request."""
    try:
        asyncio.run(coro)
        return None
    except Exception as exc:
        logger.exception("Prefect sync failed")
        return SYNC_WARNING.format(error=type(exc).__name__)


def job_or_404(db: Session, job_id: int) -> Job:
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def apply_body(db: Session, job: Job, body: JobBody) -> None:
    keyword = body.keyword.strip()
    if not keyword or len(keyword) > 512:
        raise HTTPException(status_code=400, detail="Search keyword is required (max 512 characters)")
    if not 1 <= body.scroll_count <= MAX_SCROLL_COUNT:
        raise HTTPException(status_code=400, detail=f"Scroll count must be between 1 and {MAX_SCROLL_COUNT}")
    try:
        tag = check_tag(db, body.tag, current=job.tag)
        cron = deployments.validate_cron(body.cron_expression.strip())
    except (TagNotAllowed, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    job.keyword = keyword
    job.scroll_count = body.scroll_count
    job.tag = tag
    job.cron_expression = cron


# ---------- endpoints ----------

@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    last_runs = latest_run_logs(db)
    counts = email_counts_by_job(db)
    return [serialize_job(j, last_runs.get(j.id), counts.get(j.id, 0)) for j in get_jobs(db)]


@router.post("", status_code=201)
def create_job(body: JobBody, db: Session = Depends(get_db)):
    job = Job(status=JobStatus.IDLE.value)
    apply_body(db, job, body)
    save_job(db, job)
    return serialize_one(db, job, push_to_prefect(deployments.sync_job(job)))


@router.put("/{job_id}")
def update_job(job_id: int, body: JobBody, db: Session = Depends(get_db)):
    job = job_or_404(db, job_id)
    apply_body(db, job, body)
    save_job(db, job)
    return serialize_one(db, job, push_to_prefect(deployments.sync_job(job)))


@router.post("/{job_id}/hold")
def hold_job(job_id: int, db: Session = Depends(get_db)):
    job = job_or_404(db, job_id)
    job.status = JobStatus.HOLD.value
    save_job(db, job)
    return serialize_one(db, job, push_to_prefect(deployments.sync_job(job)))


@router.post("/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db)):
    job = job_or_404(db, job_id)
    if job.status != JobStatus.HOLD:
        raise HTTPException(status_code=400, detail="Job is not on hold")
    job.status = JobStatus.IDLE.value
    save_job(db, job)
    return serialize_one(db, job, push_to_prefect(deployments.sync_job(job)))


@router.post("/{job_id}/run", status_code=202)
def run_job(job_id: int, db: Session = Depends(get_db)):
    job = job_or_404(db, job_id)
    if job.status == JobStatus.HOLD:
        raise HTTPException(status_code=400, detail="Resume the job before running it")

    async def sync_and_run() -> str:
        # Upsert first so a job created while Prefect was down can still run.
        await deployments.sync_job(job)
        return await deployments.run_job_now(job.id)

    try:
        flow_run_id = asyncio.run(sync_and_run())
    except Exception as exc:
        logger.exception("Could not start job run")
        raise HTTPException(status_code=502, detail=f"Could not reach Prefect to start the run ({type(exc).__name__})")
    return {"flow_run_id": flow_run_id, "detail": "Run started"}


@router.get("/{job_id}/runs")
def job_runs(job_id: int, db: Session = Depends(get_db)):
    job_or_404(db, job_id)
    return [serialize_run(r) for r in get_run_logs(db, job_id)]


@router.delete("/{job_id}")
def remove_job(job_id: int, db: Session = Depends(get_db)):
    job_or_404(db, job_id)
    delete_job(db, job_id)
    return {"warning": push_to_prefect(deployments.delete_job_deployment(job_id))}
