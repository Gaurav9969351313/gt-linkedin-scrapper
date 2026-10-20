import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import LinkedInCheckpointError
from gt_linkedin_scraper.crawler.browser import BrowserPool
from gt_linkedin_scraper.crawler.linkedin import LinkedInCrawler
from gt_linkedin_scraper.crawler.parser import Parser
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.extraction import EmailRecord, PostRecord
from gt_linkedin_scraper.models.job import Job
from gt_linkedin_scraper.notifier.emailer import EmailNotifier
from gt_linkedin_scraper.storage.repository import (
    CandidateRepository,
    EmailRepository,
    JobRepository,
    PostRepository,
)

logger = logging.getLogger(__name__)


async def _notify(job: Job, emails_csv: Path, email_count: int) -> None:
    from gt_linkedin_scraper.notifier.emailer import (
        render_report_html,
        render_report_text,
        report_subject,
    )

    if email_count == 0:
        logger.info("No emails scraped, skipping report", extra={"job_id": job.id})
        return

    try:
        notifier = EmailNotifier()
        today = datetime.now().strftime("%d-%m-%Y")
        subject = report_subject(job.tag, email_count)
        html_body = render_report_html(job.keyword, job.tag, email_count, today, emails_csv.name)
        text_body = render_report_text(job.keyword, job.tag, email_count, today, emails_csv.name)
        recipients = notifier._get_recipients(job.tag)
    except Exception as exc:
        logger.error(
            "Notification failed",
            extra={"job_id": job.id, "error": str(exc)},
            exc_info=True,
        )
        return

    for recipient in recipients:
        try:
            await notifier.send_with_attachments(
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                attachments=[emails_csv],
                recipient=recipient,
            )
        except Exception as exc:
            logger.error(
                "Report email failed",
                extra={"job_id": job.id, "recipient": recipient, "error": str(exc)},
            )

logger = logging.getLogger(__name__)


async def run_job(job_id: int, db: AsyncSession) -> None:
    job_repo = JobRepository(db)
    email_repo = EmailRepository(db)
    post_repo = PostRepository(db)

    job = await job_repo.get_by_id(job_id)
    if job is None:
        logger.error("Job not found", extra={"job_id": job_id})
        return

    if job.status == JobStatus.HOLD:
        logger.info("Job on hold, skipping", extra={"job_id": job_id})
        return

    await job_repo.update_status(job_id, JobStatus.RUNNING)
    await job_repo.add_run_log(job_id, JobStatus.RUNNING)

    html = ""
    try:
        async with BrowserPool() as pool:
            async with await pool.new_context() as context:
                page = await context.new_page()
                crawler = LinkedInCrawler(context)
                await crawler.ensure_login(page)
                await crawler.navigate_to_search(page, job.keyword)
                html = await crawler.scroll_and_collect(page, job.scroll_count)
    except LinkedInCheckpointError as exc:
        logger.error("Checkpoint detected", extra={"job_id": job_id, "error": str(exc)})
        await job_repo.update_status(job_id, JobStatus.ERROR)
        await job_repo.add_run_log(job_id, JobStatus.ERROR, error_message=str(exc))
        await db.commit()
        return
    except Exception as exc:
        logger.error("Job failed", extra={"job_id": job_id, "error": str(exc)}, exc_info=True)
        await job_repo.update_status(job_id, JobStatus.ERROR)
        await job_repo.add_run_log(job_id, JobStatus.ERROR, error_message=str(exc))
        await db.commit()
        return

    try:
        emails = Parser.extract_emails(html)
        unique_emails = list(dict.fromkeys(emails))
        email_records = [
            EmailRecord(job_id=job.id, tag=job.tag, email=email, source_post_content="")
            for email in unique_emails
        ]
        await email_repo.add_many(email_records)

        posts = Parser.extract_posts(html, job.id)
        post_records = [
            PostRecord(
                job_id=job.id,
                username=p["username"],
                content=p["content"],
                emails_found=p["emails_found"],
            )
            for p in posts
        ]
        await post_repo.add_many(post_records)

        extract_dir = Path("extract")
        csv_records = posts + [
            {"username": "", "emails_found": email, "content": ""}
            for email in unique_emails
        ]
        emails_csv, email_count = Parser.write_csvs(csv_records, job.keyword, job.tag, extract_dir)

        await job_repo.update_status(job_id, JobStatus.COMPLETED)
        await job_repo.add_run_log(
            job_id, JobStatus.COMPLETED,
            records_count=len(unique_emails) + len(posts),
        )
        await db.commit()
        logger.info(
            "Job completed",
            extra={"job_id": job_id, "emails": len(unique_emails), "posts": len(posts)},
        )
        await _notify(job, emails_csv, email_count)
    except Exception as exc:
        logger.error(
            "Post-processing failed",
            extra={"job_id": job_id, "error": str(exc)},
            exc_info=True,
        )
        await job_repo.update_status(job_id, JobStatus.ERROR)
        await job_repo.add_run_log(job_id, JobStatus.ERROR, error_message=str(exc))
        await db.commit()


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
