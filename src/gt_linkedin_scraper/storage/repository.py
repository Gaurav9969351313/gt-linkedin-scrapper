from datetime import datetime
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from gt_linkedin_scraper.models.job import Job, RunLog
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.extraction import EmailRecord, PostRecord


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, limit: int = 100, offset: int = 0, status: Optional[str] = None):
        stmt = select(Job).limit(limit).offset(offset)
        if status:
            stmt = stmt.where(Job.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, job_id: int) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, keyword: str, scroll_count: int, tag: str, cron_expression: str) -> Job:
        job = Job(
            keyword=keyword,
            scroll_count=scroll_count,
            tag=tag,
            cron_expression=cron_expression,
            status=JobStatus.IDLE,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_status(self, job_id: int, new_status: JobStatus) -> Optional[Job]:
        job = await self.get_by_id(job_id)
        if job is None:
            return None
        job.status = new_status
        await self.session.flush()
        return job

    async def delete(self, job_id: int) -> bool:
        job = await self.get_by_id(job_id)
        if job is None:
            return False
        await self.session.delete(job)
        await self.session.flush()
        return True

    async def add_run_log(self, job_id: int, status: JobStatus, error_message: Optional[str] = None, records_count: Optional[int] = None) -> RunLog:
        run_log = RunLog(
            job_id=job_id,
            status=status,
            error_message=error_message,
            records_count=records_count,
            finished_at=datetime.utcnow() if status in (JobStatus.COMPLETED, JobStatus.ERROR) else None,
        )
        self.session.add(run_log)
        await self.session.flush()
        return run_log

    async def get_run_logs(self, job_id: int, limit: int = 50, offset: int = 0):
        stmt = select(RunLog).where(RunLog.job_id == job_id).order_by(desc(RunLog.started_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class EmailRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, limit: int = 100, offset: int = 0, job_id: Optional[int] = None):
        stmt = select(EmailRecord).limit(limit).offset(offset)
        if job_id:
            stmt = stmt.where(EmailRecord.job_id == job_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, email_record: EmailRecord) -> EmailRecord:
        self.session.add(email_record)
        await self.session.flush()
        return email_record

    async def add_many(self, records: list[EmailRecord]) -> None:
        self.session.add_all(records)
        await self.session.flush()


class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, limit: int = 100, offset: int = 0, job_id: Optional[int] = None):
        stmt = select(PostRecord).limit(limit).offset(offset)
        if job_id:
            stmt = stmt.where(PostRecord.job_id == job_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, post_record: PostRecord) -> PostRecord:
        self.session.add(post_record)
        await self.session.flush()
        return post_record

    async def add_many(self, records: list[PostRecord]) -> None:
        self.session.add_all(records)
        await self.session.flush()
