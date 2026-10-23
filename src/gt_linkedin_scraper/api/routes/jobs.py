from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from gt_linkedin_scraper.core.database import get_db
from gt_linkedin_scraper.api.dependencies import get_job_repo
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.scheduler.deployments import delete_job_deployment, sync_job, validate_cron
from gt_linkedin_scraper.storage.tags import async_active_tag_names
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


router = APIRouter()


class JobCreate(BaseModel):
    keyword: str
    scroll_count: int
    tag: str
    cron: str


class JobResponse(BaseModel):
    id: int
    keyword: str
    scroll_count: int
    tag: str
    cron_expression: str
    status: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RunLogResponse(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    records_count: Optional[int]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[JobResponse])
async def list_jobs(status: Optional[str] = None, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    jobs = await repo.get_all(limit=1000, status=status)
    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/", response_model=JobResponse)
async def create_job(job_in: JobCreate, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    if job_in.tag not in await async_active_tag_names(db):
        raise HTTPException(status_code=422, detail=f"Unknown or inactive tag '{job_in.tag}'")
    try:
        validate_cron(job_in.cron)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    job = await repo.create(job_in.keyword, job_in.scroll_count, job_in.tag, job_in.cron)
    await sync_job(job)
    return JobResponse.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    ok = await repo.delete(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    await delete_job_deployment(job_id)
    return {"detail": "deleted"}


@router.post("/{job_id}/hold")
async def hold_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.update_status(job_id, JobStatus.HOLD)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await sync_job(job)  # pauses the schedule
    return {"detail": "held"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.update_status(job_id, JobStatus.IDLE)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await sync_job(job)  # resumes the schedule
    return {"detail": "resumed"}


@router.post("/{job_id}/retry")
async def retry_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.update_status(job_id, JobStatus.IDLE)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"detail": "retry scheduled"}


@router.get("/{job_id}/runs", response_model=List[RunLogResponse])
async def get_job_runs(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    logs = await repo.get_run_logs(job_id, limit=100)
    return [RunLogResponse.model_validate(log) for log in logs]
