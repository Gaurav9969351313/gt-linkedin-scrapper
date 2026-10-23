"""Tag management (super admin only), plus the active-tag list every signed-in user needs."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.tag import TAG_NAME_PATTERN, Tag
from gt_linkedin_scraper.storage.tags import get_tag, list_tags, tag_usage
from gt_linkedin_scraper.web.security import current_user, require_super_admin

router = APIRouter(tags=["tags"])

EMPTY_USAGE = {"jobs": 0, "candidates": 0, "email_records": 0}


class TagCreate(BaseModel):
    name: str
    label: str
    description: Optional[str] = None


class TagUpdate(BaseModel):
    label: str
    description: Optional[str] = None
    is_active: bool = True


def serialize_tag(tag: Tag, usage: Optional[dict] = None) -> dict:
    data = {
        "id": tag.id,
        "name": tag.name,
        "label": tag.label,
        "description": tag.description,
        "is_active": tag.is_active,
    }
    if usage is not None:
        data["usage"] = usage.get(tag.name, EMPTY_USAGE)
    return data


def _clean_label(label: str) -> str:
    label = label.strip()
    if not label or len(label) > 128:
        raise HTTPException(status_code=400, detail="Label is required (max 128 characters)")
    return label


@router.get("/tags", dependencies=[Depends(current_user)])
def active_tags(db: Session = Depends(get_db)):
    """Tags that can be chosen for new candidates and jobs."""
    return [serialize_tag(t) for t in list_tags(db, active_only=True)]


@router.get("/admin/tags", dependencies=[Depends(require_super_admin)])
def all_tags(db: Session = Depends(get_db)):
    usage = tag_usage(db)
    return [serialize_tag(t, usage) for t in list_tags(db)]


@router.post("/admin/tags", status_code=201, dependencies=[Depends(require_super_admin)])
def create_tag(body: TagCreate, db: Session = Depends(get_db)):
    name = body.name.strip().lower()
    if not re.match(TAG_NAME_PATTERN, name):
        raise HTTPException(
            status_code=400,
            detail="Name must be lowercase letters, digits or underscores (max 64), starting with a letter or digit",
        )
    if get_tag(db, name):
        raise HTTPException(status_code=409, detail=f"Tag '{name}' already exists")
    tag = Tag(name=name, label=_clean_label(body.label), description=(body.description or "").strip() or None)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return serialize_tag(tag, tag_usage(db))


@router.put("/admin/tags/{tag_id}", dependencies=[Depends(require_super_admin)])
def update_tag(tag_id: int, body: TagUpdate, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.label = _clean_label(body.label)
    tag.description = (body.description or "").strip() or None
    tag.is_active = body.is_active
    db.commit()
    db.refresh(tag)
    return serialize_tag(tag, tag_usage(db))


@router.delete("/admin/tags/{tag_id}", status_code=204, dependencies=[Depends(require_super_admin)])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    usage = tag_usage(db).get(tag.name, EMPTY_USAGE)
    if usage["jobs"] or usage["candidates"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{tag.label}' is used by {usage['jobs']} job(s) and {usage['candidates']} candidate(s). "
                "Move them to another tag first, or deactivate this tag instead."
            ),
        )
    db.delete(tag)
    db.commit()
