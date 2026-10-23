import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import JobNotFoundError, LinkedInCheckpointError, LoginFailed
from gt_linkedin_scraper.crawler.browser import BrowserPool
from gt_linkedin_scraper.crawler.linkedin import LinkedInCrawler
from gt_linkedin_scraper.crawler.parser import Parser
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.extraction import EmailRecord, PostRecord
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.notifier.emailer import EmailNotifier
from gt_linkedin_scraper.scheduler.progress import RunSteps
from gt_linkedin_scraper.storage.repository import (
    CandidateRepository,
    EmailRepository,
    JobRepository,
    PostRepository,
)

logger = logging.getLogger(__name__)


async def _notify(job: Job, records_count: int, extract_dir: Path) -> None:
    try:
        from gt_linkedin_scraper.notifier.emailer import render_report_html, render_report_text

        today = datetime.now().strftime("%d-%m-%Y")
        safe_keyword = job.keyword.replace(" ", "_").replace('"', "")
        attachments = [
            extract_dir / today / f"{safe_keyword}_emails.csv",
            extract_dir / today / f"post_details_{safe_keyword}.csv",
        ]
        attachments = [p for p in attachments if p.exists()]

        notifier = EmailNotifier()
        html_body = render_report_html(job.keyword, job.tag, records_count, today)
        text_body = render_report_text(job.keyword, job.tag, records_count, today)
        await notifier.send_with_attachments(
            subject=f"Scraper Report: {job.keyword}",
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
        )
    except Exception as exc:
        logger.error(
            "Notification failed",
            extra={"job_id": job.id, "error": str(exc)},
            exc_info=True,
        )

# What to tell the person reading the run log when a step fails.
FAILURE_HINTS = {
    LinkedInCheckpointError: "Sign in to the LinkedIn account in a normal browser, complete the security check, then run the job again.",
    LoginFailed: "Check LINKEDIN_USERNAME / LINKEDIN_PASSWORD in .env. Screenshots and HTML of the login page are in runtime/debug/.",
}


def _sample(items: list[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


async def run_job(job_id: int, db: AsyncSession) -> dict:
    """Runs one scrape job, logging every step (visible in the Prefect run's Logs tab) and
    attaching a summary report (Artifacts tab). Returns {"job_id", "status", "emails", "posts", "error"}."""
    job_repo = JobRepository(db)
    email_repo = EmailRepository(db)
    post_repo = PostRepository(db)
    steps = RunSteps(f"Scrape job #{job_id}", total=8)
    result = {"job_id": job_id, "status": "error", "emails": 0, "posts": 0, "error": None}
    job = None

    try:
        with steps.step("Load job settings"):
            job = await job_repo.get_by_id(job_id)
            if job is None:
                raise JobNotFoundError(f"Job #{job_id} does not exist (it may have been deleted)")
            steps.info(f"Search: {job.keyword}")
            steps.info(f"Tag: {job.tag} · scrolls: {job.scroll_count} · schedule: {job.cron_expression} · status: {job.status}")

        if job.status == JobStatus.HOLD:
            steps.skip_remaining("the job is on hold")
            steps.finish("Skipped: job is on hold")
            result["status"] = "skipped"
            await steps.publish_report(f"scrape-job-{job_id}")
            return result

        await job_repo.update_status(job_id, JobStatus.RUNNING)
        await job_repo.add_run_log(job_id, JobStatus.RUNNING)
        await db.commit()  # so the web app shows "Running" while the scrape is in progress

        with steps.step("Start headless browser"):
            pool = BrowserPool()
            await pool.start()
            context = await pool.new_context()
            page = await context.new_page()
        try:
            crawler = LinkedInCrawler(context)
            with steps.step("Log in to LinkedIn"):
                await crawler.ensure_login(page)
            with steps.step("Open LinkedIn search results (posts from the past 24 hours)"):
                await crawler.navigate_to_search(page, job.keyword)
            with steps.step(f"Scroll the results {job.scroll_count} times and collect posts"):
                html = await crawler.scroll_and_collect(page, job.scroll_count, progress=steps.info)
        finally:
            await context.close()
            await pool.stop()

        with steps.step("Extract HR emails and posts"):
            unique_emails = list(dict.fromkeys(Parser.extract_emails(html)))
            posts = Parser.extract_posts(html, job.id)
            steps.info(f"{len(unique_emails)} unique email address(es) found")
            if unique_emails:
                steps.info(f"Emails: {_sample(unique_emails)}")
            steps.info(f"{len(posts)} post(s) parsed")
            if not unique_emails:
                steps.warning("No emails found. Try a broader search or more scrolls.")

        with steps.step("Save results to the database"):
            await email_repo.add_many(
                [EmailRecord(job_id=job.id, tag=job.tag, email=e, source_post_content="") for e in unique_emails]
            )
            await post_repo.add_many(
                [
                    PostRecord(job_id=job.id, username=p["username"], content=p["content"], emails_found=p["emails_found"])
                    for p in posts
                ]
            )
            steps.info(f"Saved {len(unique_emails)} email record(s) and {len(posts)} post(s) with tag '{job.tag}'")

        with steps.step("Write CSV extracts"):
            csv_records = posts + [{"username": "", "emails_found": e, "content": ""} for e in unique_emails]
            emails_file, posts_file = Parser.write_csvs(csv_records, job.keyword, job.tag, Path(settings.extract_dir))
            steps.info(f"Emails CSV: {emails_file}")
            steps.info(f"Posts CSV: {posts_file}")

        # Email notifications skipped for now
        # await _notify(job, len(unique_emails) + len(posts), Path(settings.extract_dir))

        await job_repo.update_status(job_id, JobStatus.COMPLETED)
        await job_repo.add_run_log(job_id, JobStatus.COMPLETED, records_count=len(unique_emails) + len(posts))
        await db.commit()

        result.update(status="completed", emails=len(unique_emails), posts=len(posts))
        steps.fact("Search", job.keyword)
        steps.fact("Tag", job.tag)
        steps.fact("Emails found", len(unique_emails))
        steps.fact("Posts parsed", len(posts))
        steps.finish(f"{len(unique_emails)} email(s) and {len(posts)} post(s) saved")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result["error"] = error
        hint = next((h for cls, h in FAILURE_HINTS.items() if isinstance(exc, cls)), None)
        if hint:
            steps.warning(f"What to do: {hint}")
        if not isinstance(exc, (LinkedInCheckpointError, LoginFailed, JobNotFoundError)):
            steps.log.error("Unexpected error", exc_info=exc)
        await db.rollback()  # drop anything half-saved by the failed step
        if job is not None:
            await job_repo.update_status(job_id, JobStatus.ERROR)
            await job_repo.add_run_log(job_id, JobStatus.ERROR, error_message=str(exc)[:1000])
            await db.commit()
        steps.fact("Error", error)
        if hint:
            steps.fact("What to do", hint)
        steps.finish(error, ok=False)

    await steps.publish_report(f"scrape-job-{job_id}")
    return result


async def fetch_active_candidates(db: AsyncSession) -> list[Candidate]:
    repo = CandidateRepository(db)
    return await repo.get_active(limit=1000)


async def fetch_candidate_by_id(db: AsyncSession, candidate_id: int) -> Candidate | None:
    repo = CandidateRepository(db)
    return await repo.get_by_id(candidate_id)


async def fetch_email_records_by_tag(db: AsyncSession, tag: str) -> list[EmailRecord]:
    stmt = select(EmailRecord).where(EmailRecord.tag == tag)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def send_email_to_recipient(
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachment_path: str | None,
    sender_email: str,
    sender_password: str,
) -> None:
    notifier = EmailNotifier(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=sender_email,
        password=sender_password,
        sender=sender_email,
    )

    attachments: list[Path] = []
    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            attachments.append(path)

    await notifier.send_with_attachments(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
        recipient=recipient,
        sender=sender_email,
    )
