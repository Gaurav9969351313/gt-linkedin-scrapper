from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.extraction import EmailRecord, PostRecord
from gt_linkedin_scraper.models.job import Job, RunLog


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Deleted jobs are soft-deleted (their scraped data is kept) and hidden unless asked for.
    async def get_all(self, limit: int = 100, offset: int = 0, status: str | None = None, include_deleted: bool = False):
        stmt = select(Job).limit(limit).offset(offset)
        if not include_deleted:
            stmt = stmt.where(Job.status != JobStatus.DELETED)
        if status:
            stmt = stmt.where(Job.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, job_id: int) -> Job | None:
        stmt = select(Job).where(Job.id == job_id, Job.status != JobStatus.DELETED)
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

    async def update_status(self, job_id: int, new_status: JobStatus) -> Job | None:
        job = await self.get_by_id(job_id)
        if job is None:
            return None
        job.status = new_status
        await self.session.flush()
        return job

    async def delete(self, job_id: int) -> bool:
        return await self.update_status(job_id, JobStatus.DELETED) is not None

    async def add_run_log(
        self,
        job_id: int,
        status: JobStatus,
        error_message: str | None = None,
        records_count: int | None = None,
    ) -> RunLog:
        run_log = RunLog(
            job_id=job_id,
            status=status,
            error_message=error_message,
            records_count=records_count,
            finished_at=datetime.utcnow()
            if status in (JobStatus.COMPLETED, JobStatus.ERROR)
            else None,
        )
        self.session.add(run_log)
        await self.session.flush()
        return run_log

    async def get_run_logs(self, job_id: int, limit: int = 50, offset: int = 0):
        stmt = (
            select(RunLog)
            .where(RunLog.job_id == job_id)
            .order_by(desc(RunLog.started_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class EmailRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, limit: int = 100, offset: int = 0, job_id: int | None = None):
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

    async def get_all(self, limit: int = 100, offset: int = 0, job_id: int | None = None):
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


class CandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, limit: int = 100, offset: int = 0):
        stmt = select(Candidate).where(Candidate.is_active).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, candidate_id: int) -> Candidate | None:
        stmt = select(Candidate).where(Candidate.id == candidate_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_tag(self, tag: str, limit: int = 100, offset: int = 0):
        stmt = select(Candidate).where(Candidate.tag == tag).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
