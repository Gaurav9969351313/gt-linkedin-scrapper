import asyncio
from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.storage.repository import JobRepository

async def main():
    session = async_session_factory()
    repo = JobRepository(session)
    jobs = await repo.get_all()
    for j in jobs:
        print(j.id, j.keyword, j.status)
    await session.close()

asyncio.run(main())
