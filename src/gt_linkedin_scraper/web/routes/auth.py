"""Public account endpoints: sign in, request access, accept an invitation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.app_user import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    AppUser,
)
from gt_linkedin_scraper.web.invitations import APP_NAME, get_valid_invitation
from gt_linkedin_scraper.web.mailer import send_email
from gt_linkedin_scraper.web.schemas import AcceptInvitation, AccessRequest, LoginRequest, serialize_user
from gt_linkedin_scraper.web.security import (
    assignable_roles,
    check_login_throttle,
    clear_failed_logins,
    current_user,
    hash_password,
    issue_token,
    normalize_email,
    record_failed_login,
    utcnow,
    validate_password,
    verify_password,
)

router = APIRouter(tags=["auth"])

STATUS_LOGIN_ERRORS = {
    STATUS_PENDING: "Your access request is waiting for admin approval.",
    STATUS_REJECTED: "Your access request was not approved. Contact an administrator.",
    STATUS_DISABLED: "Your account has been disabled. Contact an administrator.",
}


def find_user_by_email(db: Session, email: str) -> AppUser | None:
    return db.scalar(select(AppUser).where(AppUser.email == email))


def admin_emails(db: Session) -> list[str]:
    stmt = select(AppUser.email).where(
        AppUser.status == STATUS_ACTIVE, AppUser.role.in_([ROLE_ADMIN, ROLE_SUPER_ADMIN])
    )
    return list(db.scalars(stmt).all())


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    check_login_throttle(email)
    user = find_user_by_email(db, email)
    if not user or not verify_password(body.password, user.password_hash):
        record_failed_login(email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Status is only revealed once the password is proven correct.
    if user.status != STATUS_ACTIVE:
        raise HTTPException(status_code=403, detail=STATUS_LOGIN_ERRORS.get(user.status, "Account is not active"))
    clear_failed_logins(email)
    user.last_login_at = utcnow()
    db.commit()
    return {"token": issue_token(user.id), "user": serialize_user(user)}


@router.get("/auth/me")
def me(user: AppUser = Depends(current_user)):
    return {**serialize_user(user), "assignable_roles": assignable_roles(user)}


@router.post("/auth/request-access", status_code=202)
def request_access(body: AccessRequest, db: Session = Depends(get_db)):
    email = normalize_email(body.email)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    validate_password(body.password)
    reason = body.reason.strip() or None

    user = find_user_by_email(db, email)
    if user and user.status != STATUS_REJECTED:
        raise HTTPException(
            status_code=409,
            detail="An account or pending request already exists for this email. Try signing in.",
        )
    if not user:
        user = AppUser(email=email)
        db.add(user)
    # A previously rejected person may ask again; it goes back into the review queue.
    user.name = name
    user.password_hash = hash_password(body.password)
    user.role = ROLE_USER
    user.status = STATUS_PENDING
    user.request_reason = reason
    user.reviewed_at = None
    user.reviewed_by_id = None
    db.commit()

    send_email(
        admin_emails(db),
        f"Access request: {name}",
        f"{name} <{email}> requested access to {APP_NAME}.\n\n"
        f"Reason: {reason or '(none given)'}\n\n"
        "Review it under Users > Access requests.",
    )
    return {"status": STATUS_PENDING, "message": "Request received. You can sign in once an admin approves it."}


@router.get("/invitations/lookup")
def lookup_invitation(token: str, db: Session = Depends(get_db)):
    invitation = get_valid_invitation(db, token)
    return {"email": invitation.email, "role": invitation.role}


@router.post("/invitations/accept")
def accept_invitation(body: AcceptInvitation, db: Session = Depends(get_db)):
    invitation = get_valid_invitation(db, body.token)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    validate_password(body.password)

    user = find_user_by_email(db, invitation.email)
    if user and user.status in (STATUS_ACTIVE, STATUS_DISABLED):
        raise HTTPException(status_code=409, detail="An account already exists for this email. Try signing in.")
    if not user:
        user = AppUser(email=invitation.email)
        db.add(user)
    user.name = name
    user.password_hash = hash_password(body.password)
    user.role = invitation.role
    user.status = STATUS_ACTIVE
    user.invited_by_id = invitation.invited_by_id
    user.reviewed_by_id = invitation.invited_by_id
    user.reviewed_at = utcnow()
    user.last_login_at = utcnow()
    invitation.accepted_at = utcnow()
    db.commit()
    db.refresh(user)
    return {"token": issue_token(user.id), "user": serialize_user(user)}
