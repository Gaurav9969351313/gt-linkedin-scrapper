"""Admin endpoints: access requests, user management and invitations."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.app_user import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUSES,
    AppInvitation,
    AppUser,
)
from gt_linkedin_scraper.web.invitations import APP_NAME, issue_invitation
from gt_linkedin_scraper.web.mailer import send_email
from gt_linkedin_scraper.web.routes.auth import find_user_by_email
from gt_linkedin_scraper.web.schemas import ApproveBody, InviteBody, RoleBody, serialize_invitation, serialize_user
from gt_linkedin_scraper.web.security import (
    ensure_can_assign,
    ensure_can_manage,
    normalize_email,
    require_admin,
    utcnow,
)

router = APIRouter(tags=["admin"])


def get_user_or_404(db: Session, user_id: int) -> AppUser:
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _manageable_user(db: Session, user_id: int, actor: AppUser, expected_status: str, action: str) -> AppUser:
    user = get_user_or_404(db, user_id)
    ensure_can_manage(actor, user)
    if user.status != expected_status:
        raise HTTPException(status_code=400, detail=f"Only {expected_status} accounts can be {action}")
    return user


# ---------- users & access requests ----------

@router.get("/users")
def list_users(
    status: Optional[str] = None, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)
):
    stmt = select(AppUser).order_by(AppUser.created_at.desc())
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail=f"Status must be one of {list(STATUSES)}")
        stmt = stmt.where(AppUser.status == status)
    return [serialize_user(u, actor) for u in db.scalars(stmt).all()]


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: int, body: ApproveBody, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)
):
    user = _manageable_user(db, user_id, actor, STATUS_PENDING, "approved")
    ensure_can_assign(actor, body.role)
    user.status = STATUS_ACTIVE
    user.role = body.role
    user.reviewed_by_id = actor.id
    user.reviewed_at = utcnow()
    db.commit()
    send_email(
        [user.email],
        f"Your {APP_NAME} access was approved",
        f"Hi {user.name},\n\nYour access request was approved. You can now sign in with the password you chose.",
    )
    return serialize_user(user, actor)


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    user = _manageable_user(db, user_id, actor, STATUS_PENDING, "rejected")
    user.status = STATUS_REJECTED
    user.reviewed_by_id = actor.id
    user.reviewed_at = utcnow()
    db.commit()
    return serialize_user(user, actor)


@router.post("/users/{user_id}/disable")
def disable_user(user_id: int, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    user = _manageable_user(db, user_id, actor, STATUS_ACTIVE, "disabled")
    user.status = STATUS_DISABLED
    db.commit()
    return serialize_user(user, actor)


@router.post("/users/{user_id}/enable")
def enable_user(user_id: int, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    user = _manageable_user(db, user_id, actor, STATUS_DISABLED, "re-enabled")
    user.status = STATUS_ACTIVE
    db.commit()
    return serialize_user(user, actor)


@router.patch("/users/{user_id}/role")
def change_role(
    user_id: int, body: RoleBody, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)
):
    user = get_user_or_404(db, user_id)
    ensure_can_manage(actor, user)
    ensure_can_assign(actor, body.role)
    user.role = body.role
    db.commit()
    return serialize_user(user, actor)


# ---------- invitations ----------

@router.get("/invitations")
def list_invitations(actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = (
        select(AppInvitation)
        .where(AppInvitation.accepted_at.is_(None), AppInvitation.revoked_at.is_(None))
        .order_by(AppInvitation.created_at.desc())
    )
    return [serialize_invitation(i, actor) for i in db.scalars(stmt).all()]


@router.post("/invitations", status_code=201)
def create_invitation(
    body: InviteBody, request: Request, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)
):
    email = normalize_email(body.email)
    ensure_can_assign(actor, body.role)
    existing = find_user_by_email(db, email)
    if existing and existing.status == STATUS_PENDING:
        raise HTTPException(
            status_code=409, detail="This person already requested access. Approve it under Access requests."
        )
    if existing and existing.status in (STATUS_ACTIVE, STATUS_DISABLED):
        raise HTTPException(status_code=409, detail="An account already exists for this email.")
    return issue_invitation(db, request, email, body.role, actor)


def _manageable_invitation(db: Session, invitation_id: int, actor: AppUser) -> AppInvitation:
    invitation = db.get(AppInvitation, invitation_id)
    if not invitation or invitation.accepted_at or invitation.revoked_at:
        raise HTTPException(status_code=404, detail="Invitation not found")
    ensure_can_assign(actor, invitation.role)
    return invitation


@router.post("/invitations/{invitation_id}/resend")
def resend_invitation(
    invitation_id: int, request: Request, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)
):
    invitation = _manageable_invitation(db, invitation_id, actor)
    return issue_invitation(db, request, invitation.email, invitation.role, actor)


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(invitation_id: int, actor: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    invitation = _manageable_invitation(db, invitation_id, actor)
    invitation.revoked_at = utcnow()
    db.commit()
