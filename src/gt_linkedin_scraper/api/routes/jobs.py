from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from gt_linkedin_scraper.core.database import get_db
from gt_linkedin_scraper.api.dependencies import get_job_repo
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.scheduler.deployer import deploy_job, undeploy_job
from prefect.client.schemas.schedules import CronSchedule
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List


router = APIRouter()


class JobCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=512)
    scroll_count: int = Field(gt=0)
    tag: str = Field(min_length=1, max_length=64)
    cron: str

    @field_validator("tag")
    @classmethod
    def normalize_tag(cls, value: str) -> str:
        # Tags key recipient env vars and candidate matching, e.g. "Data Engineer" -> "data_engineer".
        tag = "_".join(value.lower().split())
        if not tag:
            raise ValueError("tag must not be blank")
        return tag

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        CronSchedule(cron=value)
        return value


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
    job = await repo.create(job_in.keyword.strip(), job_in.scroll_count, job_in.tag, job_in.cron)
    await db.commit()
    await db.refresh(job)
    try:
        await deploy_job(job)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Job {job.id} saved but its Prefect deployment failed; it will be retried on next API start",
        )
    return JobResponse.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    if await repo.get_by_id(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # Remove the schedule first so a failure never leaves a deployment pointing at a missing job.
    try:
        await undeploy_job(job_id)
    except Exception:
        raise HTTPException(status_code=502, detail=f"Could not delete Prefect deployment for job {job_id}; job kept")
    await repo.delete(job_id)
    return {"detail": "deleted"}


@router.post("/{job_id}/hold")
async def hold_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.update_status(job_id, JobStatus.HOLD)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"detail": "held"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int, repo=Depends(get_job_repo), db: AsyncSession = Depends(get_db)):
    job = await repo.update_status(job_id, JobStatus.IDLE)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
