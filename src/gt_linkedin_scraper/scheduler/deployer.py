import logging
from pathlib import Path

import yaml
from sqlalchemy import text
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.server.schemas.filters import FlowFilter, FlowFilterName

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.models.enums import JobStatus, Tag
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.scheduler.flows import hr_email_dispatcher, scrape_single_flow
from gt_linkedin_scraper.storage.repository import JobRepository

logger = logging.getLogger(__name__)


def _ensure_tag(tag_str: str) -> str:
    try:
        return Tag(tag_str).value
    except ValueError:
        return Tag.JAVA.value


async def _get_flow_id(client) -> str:
    flows = await client.read_flows(
        flow_filter=FlowFilter(name=FlowFilterName(like_=scrape_single_flow.name))
    )
    if flows:
        return flows[0].id
    return await client.create_flow_from_name(scrape_single_flow.name)


async def _get_email_flow_id(client) -> str:
    flows = await client.read_flows(
        flow_filter=FlowFilter(name=FlowFilterName(like_=hr_email_dispatcher.name))
    )
    if flows:
        return flows[0].id
    return await client.create_flow_from_name(hr_email_dispatcher.name)


async def _ensure_deployment(job: Job, client, flow_id: str) -> None:
    name = f"scrape-job-{job.id}"
    schedule = {"cron": job.cron_expression, "timezone": "Asia/Kolkata"}

    try:
        deployment = await client.read_deployment_by_name(name)
        if deployment:
            await client.update_deployment(
                deployment_id=deployment.id,
                deployment={
                    "schedules": [{"schedule": schedule}],
                    "work_pool_name": "default",
                },
            )
            logger.info("Updated deployment", extra={"job_id": job.id, "deployment_name": name})
            return
    except Exception:
        pass

    try:
        await client.create_deployment(
            flow_id=flow_id,
            name=name,
            parameters={"job_id": job.id},
            schedules=[{"schedule": schedule}],
            tags=["linkedin", job.tag],
            entrypoint="gt_linkedin_scraper.scheduler.flows:scrape_single_flow",
            work_pool_name="default",
        )
        logger.info("Created deployment", extra={"job_id": job.id, "deployment_name": name})
    except Exception:
        logger.exception(
            "Failed to create deployment",
            extra={"job_id": job.id, "deployment_name": name},
        )
        raise


async def deploy_job(job: Job) -> None:
    async with get_client() as client:
        flow_id = await _get_flow_id(client)
        await _ensure_deployment(job, client, flow_id)


async def undeploy_job(job_id: int) -> None:
    name = f"{scrape_single_flow.name}/scrape-job-{job_id}"
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            return
        await client.delete_deployment(deployment.id)
    logger.info("Deleted deployment", extra={"job_id": job_id, "deployment_name": name})


async def _ensure_email_dispatcher_deployment(client, flow_id: str) -> None:
    name = "hr-email-dispatcher"
    schedule = {"cron": "0 5 * * *", "timezone": "Asia/Kolkata"}

    try:
        deployment = await client.read_deployment_by_name(name)
        if deployment:
            await client.update_deployment(
                deployment_id=deployment.id,
                deployment={
                    "schedules": [{"schedule": schedule}],
                    "work_pool_name": "default",
                },
            )
            logger.info("Updated email dispatcher deployment", extra={"deployment_name": name})
            return
    except Exception:
        pass

    try:
        await client.create_deployment(
            flow_id=flow_id,
            name=name,
            parameters={},
            schedules=[{"schedule": schedule}],
            tags=["email", "hr"],
            entrypoint="gt_linkedin_scraper.scheduler.flows:hr_email_dispatcher",
            work_pool_name="default",
        )
        logger.info("Created email dispatcher deployment", extra={"deployment_name": name})
    except Exception:
        logger.exception(
            "Failed to create email dispatcher deployment",
            extra={"deployment_name": name},
        )


async def _reconcile() -> None:
    config_path = Path(settings.jobs_config_path)
    if not config_path.exists():
        logger.warning("Jobs config not found", extra={"path": str(config_path)})
        return

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    job_defs = data.get("jobs", [])

    async with async_session_factory() as db:
        repo = JobRepository(db)
        existing_jobs = await repo.get_all(limit=1000, include_deleted=True)
        existing_map = {j.id: j for j in existing_jobs}

        for jd in job_defs:
            tag = _ensure_tag(jd.get("tag", "java"))
            if jd["id"] in existing_map:
                job = existing_map[jd["id"]]
                job.keyword = jd["keyword"]
                job.scroll_count = jd.get("scroll_count", 10)
                job.tag = tag
                job.cron_expression = jd.get("cron", "")
            else:
                job = Job(
                    id=jd["id"],
                    keyword=jd["keyword"],
                    scroll_count=jd.get("scroll_count", 10),
                    tag=tag,
                    cron_expression=jd.get("cron", ""),
                    status=JobStatus.IDLE,
                )
                db.add(job)

        # Jobs added from the UI/API are not in the YAML, so they are kept rather than deleted.
        await db.flush()
        # YAML jobs insert explicit ids, which bypass the serial; realign it so new jobs don't collide.
        await db.execute(
            text("SELECT setval(pg_get_serial_sequence('jobs', 'id'), COALESCE((SELECT MAX(id) FROM jobs), 1))")
        )
        await db.commit()

        refreshed_jobs = await repo.get_all(limit=1000)

    active_jobs = [job for job in refreshed_jobs if job.status != JobStatus.HOLD]
    if not active_jobs:
        return

    async with get_client() as client:
        flow_id = await _get_flow_id(client)
        for job in active_jobs:
            try:
                await _ensure_deployment(job, client, flow_id)
            except Exception:
                continue

        email_flow_id = await _get_email_flow_id(client)
        await _ensure_email_dispatcher_deployment(client, email_flow_id)

    logger.info("Deployments reconciled", extra={"count": len(active_jobs)})


async def run_deployer() -> None:
    await _reconcile()
