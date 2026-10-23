"""Request bodies and response serializers for the web API."""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from gt_linkedin_scraper.models.app_user import ROLE_SUPER_ADMIN, ROLE_USER, AppInvitation, AppUser
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.web.security import assignable_roles, utcnow


# ---------- request bodies ----------

class LoginRequest(BaseModel):
    email: str
    password: str


class AccessRequest(BaseModel):
    name: str
    email: str
    password: str
    reason: str = ""


class AcceptInvitation(BaseModel):
    token: str
    name: str
    password: str


class ApproveBody(BaseModel):
    role: str = ROLE_USER


class RoleBody(BaseModel):
    role: str


class InviteBody(BaseModel):
    email: str
    role: str = ROLE_USER


# ---------- serializers ----------

def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def as_utc(value: datetime) -> datetime:
    # SQLite (tests) drops tzinfo; Postgres keeps it.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def serialize_user(user: AppUser, actor: Optional[AppUser] = None) -> dict:
    data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "request_reason": user.request_reason,
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
        "reviewed_at": _iso(user.reviewed_at),
    }
    if actor is not None:
        data["can_manage"] = actor.id != user.id and (actor.role == ROLE_SUPER_ADMIN or user.role == ROLE_USER)
    return data


def serialize_invitation(inv: AppInvitation, actor: AppUser) -> dict:
    return {
        "id": inv.id,
        "email": inv.email,
        "role": inv.role,
        "created_at": _iso(inv.created_at),
        "expires_at": inv.expires_at.isoformat(),
        "expired": as_utc(inv.expires_at) < utcnow(),
        "can_manage": inv.role in assignable_roles(actor),
    }


def serialize_candidate(c: Candidate, owner_email: Optional[str] = None) -> dict:
    # email_password is write-only and never sent to the browser.
    return {
        "owner_id": c.owner_id,
        "owner_email": owner_email,
        "id": c.id,
        "name": c.name,
        "number": c.number,
        "subscription": c.subscription,
        "is_active": c.is_active,
        "email": c.email,
        "email_subject": c.email_subject,
        "email_body": c.email_body,
        "resume": c.resume,
        "tag": c.tag,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }
