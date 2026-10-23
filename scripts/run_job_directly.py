import asyncio
import logging
from uuid import UUID

from dotenv import load_dotenv
from prefect import get_client

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

logger = logging.getLogger(__name__)


async def trigger_job(job_id: int) -> UUID | None:
    """Trigger a scrape job by creating a Prefect flow run from its deployment."""
    async with get_client() as client:
        deployment_name = f"scrape-single-job/scrape-job-{job_id}"
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except Exception:
            logger.error(
                "Deployment not found: %s — ensure the API service has started "
                "and reconciled deployments via the deployer on startup.",
                deployment_name,
            )
            return None

        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"scrape-job-{job_id}-manual",
        )
        logger.info("Triggered flow run %s for job %d", flow_run.id, job_id)
        return flow_run.id


async def wait_for_flow_run(flow_run_id: UUID, poll_interval: int = 10) -> None:
    """Poll a flow run until it reaches a terminal state."""
    async with get_client() as client:
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            state = flow_run.state
            if state is None:
                logger.info("Flow run has no state yet, waiting...")
            elif state.is_running():
                logger.info("Flow run is running (state=%s)", state.type)
            elif state.is_completed():
                logger.info("Flow run completed")
                return
            elif state.is_failed():
                logger.error("Flow run failed")
                return
            elif state.is_cancelled():
                logger.info("Flow run cancelled")
                return
            await asyncio.sleep(poll_interval)


async def main() -> None:
    job_id = 1
    print(f"Triggering job {job_id} via Prefect...")
    flow_run_id = await trigger_job(job_id)
    if flow_run_id:
        print(f"Flow run {flow_run_id} created — monitoring status...")
        await wait_for_flow_run(flow_run_id)
        print(f"Job {job_id} triggered via Prefect")
    else:
        print(f"Failed to trigger job {job_id}")


if __name__ == "__main__":
    asyncio.run(main())
