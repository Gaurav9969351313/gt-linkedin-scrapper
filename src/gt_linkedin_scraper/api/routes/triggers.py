import logging

from fastapi import APIRouter, Depends, HTTPException
from prefect import get_client

from gt_linkedin_scraper.api.dependencies import get_job_repo
from gt_linkedin_scraper.models.enums import JobStatus

logger = logging.getLogger(__name__)
router = APIRouter()


async def _create_flow_run(job_id: int) -> str:
    async with get_client() as client:
        deployment_name = f"scrape-single-job/scrape-job-{job_id}"
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Deployment {deployment_name} not found — "
                    "ensure the deployer has reconciled"
                ),
            )
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"scrape-job-{job_id}-api",
        )
        return str(flow_run.id)


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
