"""Issuing and validating invitation links."""
from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.models.app_user import AppInvitation, AppUser
from gt_linkedin_scraper.web.mailer import send_email
from gt_linkedin_scraper.web.schemas import as_utc, serialize_invitation
from gt_linkedin_scraper.web.security import hash_invite_token, new_invite_token, utcnow

APP_NAME = "LinkedIn Scraper Console"


def public_url(request: Request) -> str:
    return settings.web_public_url.rstrip("/") or str(request.base_url).rstrip("/")


def issue_invitation(db: Session, request: Request, email: str, role: str, inviter: AppUser) -> dict:
    # Re-inviting the same address replaces any outstanding invitation.
    for old in db.scalars(
        select(AppInvitation).where(
            AppInvitation.email == email,
            AppInvitation.accepted_at.is_(None),
            AppInvitation.revoked_at.is_(None),
        )
    ):
        old.revoked_at = utcnow()

    raw, token_hash = new_invite_token()
    invitation = AppInvitation(
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by_id=inviter.id,
        expires_at=utcnow() + timedelta(days=settings.web_invite_ttl_days),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    link = f"{public_url(request)}/accept-invite?token={raw}"
    sent = send_email(
        [email],
        f"You're invited to {APP_NAME}",
        f"{inviter.name} invited you to {APP_NAME} as {role.replace('_', ' ')}.\n\n"
        f"Set your password and sign in here (valid for {settings.web_invite_ttl_days} days):\n{link}\n\n"
        "If you weren't expecting this, you can ignore this email.",
    )
    return {"invitation": serialize_invitation(invitation, inviter), "invite_url": link, "email_sent": sent}


def get_valid_invitation(db: Session, token: str) -> AppInvitation:
    invitation = db.scalar(select(AppInvitation).where(AppInvitation.token_hash == hash_invite_token(token)))
    if not invitation or invitation.revoked_at or invitation.accepted_at:
        raise HTTPException(status_code=404, detail="This invitation link is invalid or has already been used.")
    if as_utc(invitation.expires_at) < utcnow():
        raise HTTPException(status_code=410, detail="This invitation has expired. Ask an admin to resend it.")
    return invitation
