"""Dashboard stats and candidates.

Access rules:
- admin / super_admin: see every candidate (the grid), create any number, edit and delete any.
- user: may create exactly one candidate (their own) and view/edit only that one.
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.app_user import ROLE_USER, AppUser
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.storage.tags import TagNotAllowed, check_tag
from gt_linkedin_scraper.storage.resumes import ALLOWED_RESUME_SUFFIXES, save_resume
from gt_linkedin_scraper.storage.sync_repository import (
    create_candidate,
    delete_candidate,
    get_candidate,
    get_candidate_by_owner,
    get_candidates,
    get_email_stats,
    update_candidate,
)
from gt_linkedin_scraper.web.schemas import serialize_candidate
from gt_linkedin_scraper.web.security import current_user, require_admin

router = APIRouter(tags=["candidates"], dependencies=[Depends(current_user)])

def is_admin(user: AppUser) -> bool:
    return user.role != ROLE_USER


def validate_tag(db: Session, tag: str, current: Optional[str] = None) -> str:
    try:
        return check_tag(db, tag, current=current)
    except TagNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def store_upload(upload: Optional[UploadFile], candidate_name: str) -> Optional[str]:
    if upload is None or not upload.filename:
        return None
    if Path(upload.filename).suffix.lower() not in ALLOWED_RESUME_SUFFIXES:
        raise HTTPException(status_code=400, detail="Resume must be a .pdf or .docx file")
    return save_resume(upload.file.read(), upload.filename, candidate_name)


def accessible_candidate(db: Session, candidate_id: int, user: AppUser) -> Candidate:
    """The candidate if this user may see it. Users get 404 for others' candidates,
    so ids of other people's candidates aren't revealed."""
    candidate = get_candidate(db, candidate_id)
    if not candidate or (not is_admin(user) and candidate.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def owner_emails(db: Session, candidates: list[Candidate]) -> dict[int, str]:
    ids = {c.owner_id for c in candidates if c.owner_id}
    if not ids:
        return {}
    return dict(db.execute(select(AppUser.id, AppUser.email).where(AppUser.id.in_(ids))).all())


def serialize(db: Session, candidate: Candidate) -> dict:
    return serialize_candidate(candidate, owner_emails(db, [candidate]).get(candidate.owner_id))


# ---------- dashboard ----------

@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    total, tag_count, tags, dates = get_email_stats(db)
    return {
        "total": total or 0,
        "tag_count": tag_count or 0,
        "by_tag": [{"tag": row.tag, "count": row.count} for row in tags],
        "by_date": [{"date": str(row.date), "count": row.count} for row in dates],
    }


# ---------- candidates ----------

@router.get("/candidates", dependencies=[Depends(require_admin)])
def list_candidates(tag: Optional[str] = None, db: Session = Depends(get_db)):
    candidates = get_candidates(db, tag)
    emails = owner_emails(db, candidates)
    return [serialize_candidate(c, emails.get(c.owner_id)) for c in candidates]


@router.get("/candidates/mine")
def my_candidate(user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    """The signed-in account's own candidate, or null if they haven't added one yet."""
    candidate = get_candidate_by_owner(db, user.id)
    return serialize(db, candidate) if candidate else None


@router.get("/candidates/{candidate_id}")
def read_candidate(candidate_id: int, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    return serialize(db, accessible_candidate(db, candidate_id, user))


@router.post("/candidates", status_code=201)
def add_candidate(
    name: str = Form(...),
    number: str = Form(...),
    subscription: str = Form(...),
    is_active: bool = Form(True),
    email: str = Form(...),
    email_password: str = Form(...),
    tag: str = Form(...),
    email_subject: str = Form(...),
    email_body: str = Form(...),
    resume_file: Optional[UploadFile] = File(None),
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not is_admin(user) and get_candidate_by_owner(db, user.id):
        raise HTTPException(status_code=409, detail="You can only create one candidature. Edit your existing one under My Candidature.")
    candidate = Candidate(
        name=name,
        number=number,
        subscription=subscription,
        is_active=is_active,
        email=email,
        email_password=email_password,
        tag=validate_tag(db, tag),
        email_subject=email_subject,
        resume=store_upload(resume_file, name),
        email_body=email_body,
        owner_id=user.id,
    )
    return serialize(db, create_candidate(db, candidate))


@router.put("/candidates/{candidate_id}")
def edit_candidate(
    candidate_id: int,
    name: str = Form(...),
    number: str = Form(...),
    subscription: str = Form(...),
    is_active: bool = Form(True),
    email: str = Form(...),
    email_password: str = Form(""),
    tag: str = Form(...),
    email_subject: str = Form(...),
    email_body: str = Form(...),
    resume_file: Optional[UploadFile] = File(None),
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    candidate = accessible_candidate(db, candidate_id, user)
    validate_tag(db, tag, current=candidate.tag)
    resume_path = store_upload(resume_file, name)
    candidate.name = name
    candidate.number = number
    candidate.subscription = subscription
    candidate.is_active = is_active
    candidate.email = email
    # Blank password means "keep the current one".
    if email_password:
        candidate.email_password = email_password
    candidate.tag = tag
    candidate.email_subject = email_subject
    if resume_path:
        candidate.resume = resume_path
    candidate.email_body = email_body
    return serialize(db, update_candidate(db, candidate_id, candidate))


@router.delete("/candidates/{candidate_id}", status_code=204, dependencies=[Depends(require_admin)])
def remove_candidate(candidate_id: int, db: Session = Depends(get_db)):
    if not delete_candidate(db, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")
