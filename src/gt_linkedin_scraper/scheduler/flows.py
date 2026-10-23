"""Prefect flows. Deployment entrypoints point at the functions below (see
scheduler/deployments.py), so keep their names and this module path stable.

Every run logs numbered steps to its Prefect Logs tab and attaches a summary report on the
Artifacts tab (scheduler/progress.py). Runs that fail end in Prefect's Failed state.
"""
import logging
from datetime import datetime
from pathlib import Path

from prefect import flow, task
from prefect.states import Completed, Failed

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.scheduler.progress import RunSteps
from gt_linkedin_scraper.scheduler.tasks import (
    fetch_active_candidates,
    fetch_candidate_by_id,
    fetch_email_records_by_tag,
    run_job,
    send_email_to_recipient,
)
from gt_linkedin_scraper.storage.repository import JobRepository

# PREFECT_LOGGING_EXTRA_LOGGERS=gt_linkedin_scraper (set on the worker) attaches Prefect's
# upload handler to our loggers, but not a level: left alone they inherit WARNING from the
# root logger and every INFO line (login, search, scrolling...) would be dropped.
logging.getLogger("gt_linkedin_scraper").setLevel(settings.log_level.upper())


def _dispatch_run_name() -> str:
    return f"hr-email-dispatcher-{datetime.now():%Y-%m-%d-%H%M}"


# ---------- scraping ----------

# No automatic retries: most failures (rejected login, security check) need a person, and
# retrying a rejected login risks locking the LinkedIn account.
@task(task_run_name="scrape-job-{job_id}")
async def scrape_job_task(job_id: int):
    async with async_session_factory() as db:
        result = await run_job(job_id, db)
    if result["status"] == "error":
        return Failed(message=result["error"], data=result)
    return result


@flow(name="scrape-single-job", flow_run_name="scrape-job-{job_id}")
async def scrape_single_flow(job_id: int):
    state = await scrape_job_task(job_id, return_state=True)
    if state.is_failed():
        return Failed(message=state.message)
    return await state.result()


@flow(name="scrape-all-jobs")
async def scrape_all_flow() -> list[dict]:
    async with async_session_factory() as db:
        jobs = await JobRepository(db).get_all(limit=1000)
    results = []
    for job in jobs:
        if job.status == JobStatus.HOLD:
            continue
        state = await scrape_job_task(job.id, return_state=True)
        results.append({"job_id": job.id, "state": state.name, "message": state.message})
    return results


# ---------- candidate emails ----------

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
) -> dict:
    steps = RunSteps(f"Emails for candidate {candidate_name} (#{candidate_id})", total=3)
    result = {"candidate_id": candidate_id, "candidate_name": candidate_name, "recipients": 0, "sent": 0, "failed": 0}

    with steps.step(f"Find HR email addresses tagged '{candidate_tag}'"):
        async with async_session_factory() as db:
            email_records = await fetch_email_records_by_tag(db, candidate_tag)
        recipients = list(dict.fromkeys(r.email for r in email_records))
        result["recipients"] = len(recipients)
        steps.info(f"{len(recipients)} unique address(es) from {len(email_records)} email record(s)")

    steps.fact("Candidate", f"{candidate_name} (#{candidate_id})")
    steps.fact("Tag", candidate_tag)
    steps.fact("Subject", candidate_email_subject)
    if not recipients:
        steps.skip_remaining(f"no HR emails have been scraped for tag '{candidate_tag}' yet")
        steps.finish("Nothing to send")
        await steps.publish_report(f"candidate-{candidate_id}-emails")
        return result

    with steps.step("Attach resume"):
        resume_path = None
        if not candidate_resume:
            steps.warning("No resume uploaded for this candidate; emails will go without an attachment")
        else:
            path = Path(settings.resume_upload_dir) / candidate_resume
            if path.exists():
                resume_path = str(path)
                steps.info(f"Attaching {path.name} ({path.stat().st_size // 1024} KB)")
            else:
                steps.warning(f"Resume file is missing at {path}; emails will go without an attachment")
        steps.fact("Resume", Path(resume_path).name if resume_path else "none")

    failures: list[tuple[str, str]] = []
    with steps.step(f"Send {len(recipients)} email(s) from {settings.smtp_user}"):
        for i, recipient in enumerate(recipients, start=1):
            try:
                await send_email_to_recipient(
                    recipient=recipient,
                    subject=candidate_email_subject,
                    html_body=candidate_email_body,
                    text_body="Please see the attached email.",
                    attachment_path=resume_path,
                    sender_email=settings.smtp_user,
                    sender_password=settings.smtp_password,
                )
                result["sent"] += 1
                steps.info(f"✉ {i}/{len(recipients)} sent to {recipient}")
            except Exception as exc:
                result["failed"] += 1
                failures.append((recipient, f"{type(exc).__name__}: {exc}"))
                steps.warning(f"✉ {i}/{len(recipients)} FAILED to {recipient}: {type(exc).__name__}: {exc}")

    steps.fact("Sent", result["sent"])
    steps.fact("Failed", result["failed"])
    if failures:
        steps.fact("Failed recipients", "; ".join(f"{r} ({e[:80]})" for r, e in failures[:20]))
    ok = result["failed"] == 0
    steps.finish(f"{result['sent']} sent, {result['failed']} failed of {len(recipients)}", ok=ok)
    await steps.publish_report(f"candidate-{candidate_id}-emails")
    if result["sent"] == 0 and failures:
        return Failed(message=f"All {len(failures)} emails failed; first error: {failures[0][1]}", data=result)
    return result


@flow(name="hr-email-dispatcher", flow_run_name=_dispatch_run_name)
async def hr_email_dispatcher(candidate_id: int | None = None):
    steps = RunSteps("HR email dispatcher", total=2)
    with steps.step("Load candidates" if candidate_id is None else f"Load candidate #{candidate_id}"):
        async with async_session_factory() as db:
            if candidate_id is not None:
                candidate = await fetch_candidate_by_id(db, candidate_id)
                if candidate is None:
                    raise ValueError(f"Candidate #{candidate_id} not found")
                if not candidate.is_active:
                    raise ValueError(f"Candidate #{candidate_id} ({candidate.name}) is inactive")
                candidates = [candidate]
            else:
                candidates = await fetch_active_candidates(db)
        steps.info(f"{len(candidates)} active candidate(s)")
        for c in candidates:
            steps.info(f"{c.name} (#{c.id}) · tag '{c.tag}' · resume: {'yes' if c.resume else 'no'}")

    results = []
    with steps.step(f"Send emails for {len(candidates)} candidate(s)"):
        for n, candidate in enumerate(candidates, start=1):
            steps.info(f"Candidate {n}/{len(candidates)}: {candidate.name} (#{candidate.id}); see its own run for details")
            state = await send_emails_for_candidate(
                candidate_id=candidate.id,
                candidate_name=candidate.name,
                candidate_tag=candidate.tag,
                candidate_email_subject=candidate.email_subject,
                candidate_email_body=candidate.email_body,
                candidate_resume=candidate.resume,
                return_state=True,
            )
            outcome = await state.result(raise_on_failure=False) if not state.is_failed() else None
            if isinstance(outcome, dict):
                steps.info(f"{candidate.name}: {outcome['sent']} sent, {outcome['failed']} failed of {outcome['recipients']}")
                results.append(outcome)
            else:
                steps.warning(f"{candidate.name}: run failed: {state.message}")
                results.append({"candidate_id": candidate.id, "candidate_name": candidate.name, "failed_run": state.message})

    sent = sum(r.get("sent", 0) for r in results)
    failed = sum(r.get("failed", 0) for r in results)
    broken = [r for r in results if "failed_run" in r]
    steps.fact("Candidates", len(candidates))
    steps.fact("Emails sent", sent)
    steps.fact("Emails failed", failed)
    steps.finish(f"{len(candidates)} candidate(s), {sent} email(s) sent, {failed} failed", ok=not broken)
    await steps.publish_report("hr-email-dispatcher")
    if broken:
        return Failed(message=f"{len(broken)} candidate run(s) failed", data=results)
    return Completed(message=f"{sent} sent, {failed} failed", data=results)
