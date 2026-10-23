import logging

from fastapi import APIRouter, Depends, HTTPException
from prefect.exceptions import ObjectNotFound

from gt_linkedin_scraper.api.dependencies import get_job_repo
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.scheduler.deployments import run_job_now

logger = logging.getLogger(__name__)
router = APIRouter()


async def _create_flow_run(job_id: int) -> str:
    try:
        return await run_job_now(job_id, run_name=f"scrape-job-{job_id}-api")
    except ObjectNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment for job {job_id} not found. Restart the API to reconcile deployments.",
        )


@router.post("/{job_id}")
async def trigger_job(job_id: int, repo=Depends(get_job_repo)):
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.HOLD:
        raise HTTPException(status_code=422, detail="Job is on hold")
    flow_run_id = await _create_flow_run(job_id)
    return {"flow_run_id": flow_run_id, "detail": "triggered"}


@router.post("/")
async def trigger_all(repo=Depends(get_job_repo)):
    jobs = await repo.get_all(limit=1000)
    results = []
    for job in jobs:
        if job.status == JobStatus.HOLD:
            continue
        flow_run_id = await _create_flow_run(job.id)
        results.append({"job_id": job.id, "flow_run_id": flow_run_id, "detail": "triggered"})
    return results
