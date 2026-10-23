import logging
import time
from pathlib import Path

from prefect import flow, task

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.scheduler.tasks import (
    fetch_active_candidates,
    fetch_candidate_by_id,
    fetch_email_records_by_tag,
    run_job,
    send_email_to_recipient,
)
from gt_linkedin_scraper.storage.repository import JobRepository

logger = logging.getLogger(__name__)

# Prefect sets the root logger to WARNING, which would drop our INFO/DEBUG logs in flow runs.
# PREFECT_LOGGING_EXTRA_LOGGERS=gt_linkedin_scraper forwards them to the Prefect UI.
logging.getLogger("gt_linkedin_scraper").setLevel(settings.log_level.upper())


def slugify_name(name: str) -> str:
    value = name.lower()
    value = "".join(ch if ch.isalnum() else "_" for ch in value)
    while "__" in value:
        value = value.replace("__", "_")
    value = value.strip("_")
    return value or "candidate"


@task(retries=3, retry_delay_seconds=[60, 120, 300])
async def scrape_job_task(job_id: int) -> dict:
    logger.info(f"Scrape task started for job {job_id}", extra={"job_id": job_id})
    start = time.perf_counter()
    async with async_session_factory() as db:
        try:
            await run_job(job_id, db)
            logger.info(
                f"Scrape task finished for job {job_id} in {time.perf_counter() - start:.1f}s",
                extra={"job_id": job_id},
            )
            return {"job_id": job_id, "status": "completed"}
        except Exception as exc:
            logger.error(f"Task failed for job {job_id}: {exc}", extra={"job_id": job_id, "error": str(exc)}, exc_info=True)
            return {"job_id": job_id, "status": "error", "error": str(exc)}


@flow(name="scrape-single-job")
async def scrape_single_flow(job_id: int) -> dict:
    logger.info(f"Flow scrape-single-job started for job {job_id} (log level {settings.log_level.upper()})")
    result = await scrape_job_task(job_id)
    logger.info(f"Flow scrape-single-job result: {result}")
    return result


@flow(name="scrape-all-jobs")
async def scrape_all_flow() -> list[dict]:
    async with async_session_factory() as db:
        repo = JobRepository(db)
        jobs = await repo.get_all(limit=1000)
    logger.info(f"Flow scrape-all-jobs found {len(jobs)} jobs")
    results = []
    for job in jobs:
        if job.status == "hold":
            logger.info(f"Skipping job {job.id} (on hold)", extra={"job_id": job.id})
            continue
        result = await scrape_job_task(job.id)
        results.append(result)
    return results


@flow(
    name="hr-email-dispatcher-candidate",
    flow_run_name="hr-email-dispatcher-candidate-{candidate_name}",
)
async def send_emails_for_candidate(
    candidate_id: int,
    candidate_name: str,
    candidate_tag: str,
    candidate_email_subject: str,
    candidate_email_body: str,
    candidate_resume: str | None,
) -> None:
    async with async_session_factory() as db:
        email_records = await fetch_email_records_by_tag(db, candidate_tag)

    if not email_records:
        logger.info(
            "No matching email records, skipping candidate",
            extra={
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "tag": candidate_tag,
            },
        )
        return

    resume_path = None
    if candidate_resume:
        path = Path("/app/ResumeUploads") / candidate_resume
        logger.debug(
            "Resume path resolution",
            extra={
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "candidate_resume": candidate_resume,
                "resolved_path": str(path),
                "exists": path.exists(),
            },
        )
        if path.exists():
            resume_path = str(path)
        else:
            logger.warning(
                "Resume attachment missing",
                extra={
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "path": str(path),
                },
            )
    else:
        logger.debug(
            "No resume configured for candidate",
            extra={
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "candidate_resume": candidate_resume,
            },
        )

    for record in email_records:
        try:
            await send_email_to_recipient(
                recipient=record.email,
                subject=candidate_email_subject,
                html_body=candidate_email_body,
                text_body="Please see the attached email.",
                attachment_path=resume_path,
                sender_email=settings.smtp_user,
                sender_password=settings.smtp_password,
            )
            logger.info(
                "Email sent",
                extra={
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "sender": settings.smtp_user,
                    "recipient": record.email,
                    "subject": candidate_email_subject,
                    "attachment": "attached" if resume_path else "missing",
                },
            )
        except Exception as exc:
            logger.error(
                "Email send failed",
                extra={
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "sender": settings.smtp_user,
                    "recipient": record.email,
                    "subject": candidate_email_subject,
                    "error": str(exc),
                },
            )


@flow(name="hr-email-dispatcher")
async def hr_email_dispatcher(candidate_id: int | None = None) -> list[dict]:
    async with async_session_factory() as db:
        if candidate_id is not None:
            candidate = await fetch_candidate_by_id(db, candidate_id)
            if candidate is None:
                logger.error("Candidate not found", extra={"candidate_id": candidate_id})
                return []
            if not candidate.is_active:
                logger.error(
                    "Candidate inactive",
                    extra={
                        "candidate_id": candidate_id,
                        "candidate_name": candidate.name,
                    },
                )
                return []
            candidates = [candidate]
        else:
            candidates = await fetch_active_candidates(db)

    results = []
    for candidate in candidates:
        logger.info(
            "Processing candidate",
            extra={
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "sender": candidate.email,
                "tag": candidate.tag,
            },
        )
        await send_emails_for_candidate(
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            candidate_tag=candidate.tag,
            candidate_email_subject=candidate.email_subject,
            candidate_email_body=candidate.email_body,
            candidate_resume=candidate.resume,
        )
        results.append({"candidate_id": candidate.id, "status": "completed"})
    return results