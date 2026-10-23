"""Keeps Prefect deployments in step with the jobs table.

One deployment per job (`scrape-single-job/scrape-job-<id>`), scheduled by the job's cron and
paused while the job is on hold. `create_deployment` is an upsert in Prefect, so syncing is
idempotent. Prefect entrypoints point at scheduler.flows; don't move those functions.
"""
import logging
from typing import Iterable, Optional

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import CronSchedule
from prefect.exceptions import ObjectNotFound

from gt_linkedin_scraper.models.enums import JobStatus

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
WORK_POOL = "default"
SCRAPE_FLOW = "scrape-single-job"
SCRAPE_ENTRYPOINT = "gt_linkedin_scraper.scheduler.flows:scrape_single_flow"
EMAIL_FLOW = "hr-email-dispatcher"
EMAIL_DEPLOYMENT = "hr-email-dispatcher"
EMAIL_ENTRYPOINT = "gt_linkedin_scraper.scheduler.flows:hr_email_dispatcher"
EMAIL_CRON = "0 5 * * *"


def deployment_name(job_id: int) -> str:
    return f"scrape-job-{job_id}"


def validate_cron(expression: str) -> str:
    """Raises ValueError if Prefect can't schedule this cron expression."""
    try:
        CronSchedule(cron=expression, timezone=TIMEZONE)
    except Exception as exc:
        raise ValueError(f"Invalid cron expression '{expression}'") from exc
    return expression


def _schedule(cron: str) -> list[DeploymentScheduleCreate]:
    return [DeploymentScheduleCreate(schedule=CronSchedule(cron=cron, timezone=TIMEZONE), active=True)]


async def upsert_job_deployment(client, job, flow_id=None) -> None:
    flow_id = flow_id or await client.create_flow_from_name(SCRAPE_FLOW)
    await client.create_deployment(
        flow_id=flow_id,
        name=deployment_name(job.id),
        entrypoint=SCRAPE_ENTRYPOINT,
        parameters={"job_id": job.id},
        schedules=_schedule(job.cron_expression),
        tags=["linkedin", job.tag],
        work_pool_name=WORK_POOL,
        paused=job.status == JobStatus.HOLD,
    )


async def delete_job_deployment_with(client, job_id: int) -> None:
    try:
        deployment = await client.read_deployment_by_name(f"{SCRAPE_FLOW}/{deployment_name(job_id)}")
    except ObjectNotFound:
        return
    await client.delete_deployment(deployment.id)


async def upsert_email_dispatcher(client) -> None:
    flow_id = await client.create_flow_from_name(EMAIL_FLOW)
    await client.create_deployment(
        flow_id=flow_id,
        name=EMAIL_DEPLOYMENT,
        entrypoint=EMAIL_ENTRYPOINT,
        parameters={},
        schedules=_schedule(EMAIL_CRON),
        tags=["email", "hr"],
        work_pool_name=WORK_POOL,
    )


async def sync_all(jobs: Iterable, prune: bool = True) -> None:
    """Upserts a deployment per job and the email dispatcher; deletes deployments of
    jobs that no longer exist (when prune=True)."""
    jobs = list(jobs)
    async with get_client() as client:
        flow_id = await client.create_flow_from_name(SCRAPE_FLOW)
        for job in jobs:
            await upsert_job_deployment(client, job, flow_id)
        if prune:
            wanted = {deployment_name(j.id) for j in jobs}
            for dep in await client.read_deployments():
                if dep.flow_id == flow_id and dep.name.startswith("scrape-job-") and dep.name not in wanted:
                    await client.delete_deployment(dep.id)
                    logger.info("Deleted orphan deployment", extra={"deployment_name": dep.name})
        await upsert_email_dispatcher(client)


async def sync_job(job) -> None:
    async with get_client() as client:
        await upsert_job_deployment(client, job)


async def delete_job_deployment(job_id: int) -> None:
    async with get_client() as client:
        await delete_job_deployment_with(client, job_id)


async def run_job_now(job_id: int, run_name: Optional[str] = None) -> str:
    """Starts a flow run of the job's deployment; returns the flow run id."""
    async with get_client() as client:
        deployment = await client.read_deployment_by_name(f"{SCRAPE_FLOW}/{deployment_name(job_id)}")
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment.id, name=run_name or f"scrape-job-{job_id}-manual"
        )
        return str(flow_run.id)
