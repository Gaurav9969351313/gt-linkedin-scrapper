from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from gt_linkedin_scraper.core.database import get_db
from gt_linkedin_scraper.storage.repository import JobRepository, EmailRepository, PostRepository


async def get_job_repo(db: AsyncSession = Depends(get_db)) -> JobRepository:
    return JobRepository(db)


async def get_email_repo(db: AsyncSession = Depends(get_db)) -> EmailRepository:
    return EmailRepository(db)


async def get_post_repo(db: AsyncSession = Depends(get_db)) -> PostRepository:
    return PostRepository(db)
