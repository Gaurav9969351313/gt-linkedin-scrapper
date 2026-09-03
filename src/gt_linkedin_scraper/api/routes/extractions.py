from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from gt_linkedin_scraper.core.database import get_db
from gt_linkedin_scraper.api.dependencies import get_email_repo, get_post_repo
from typing import List, Optional

router = APIRouter()


@router.get("/emails")
async def list_emails(
    job_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    repo=Depends(get_email_repo),
    db: AsyncSession = Depends(get_db),
):
    records = await repo.get_all(limit=limit, offset=offset, job_id=job_id)
    return [
        {
            "id": r.id,
            "job_id": r.job_id,
            "email": r.email,
            "source_post_content": r.source_post_content,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
        }
        for r in records
    ]


@router.get("/posts")
async def list_posts(
    job_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    repo=Depends(get_post_repo),
    db: AsyncSession = Depends(get_db),
):
    records = await repo.get_all(limit=limit, offset=offset, job_id=job_id)
    return [
        {
            "id": r.id,
            "job_id": r.job_id,
            "username": r.username,
            "content": r.content,
            "emails_found": r.emails_found,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
        }
        for r in records
    ]


@router.get("/emails/export.csv")
async def export_emails_csv(
    job_id: Optional[int] = None,
    repo=Depends(get_email_repo),
    db: AsyncSession = Depends(get_db),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    records = await repo.get_all(limit=10000, offset=0, job_id=job_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Email"])
    for r in records:
        writer.writerow([r.email])

    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=emails.csv"})
