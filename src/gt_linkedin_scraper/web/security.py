"""Password hashing, session tokens and role checks for the web app."""
import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.sync_database import get_db
from gt_linkedin_scraper.models.app_user import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    AppUser,
)

TOKEN_TTL_SECONDS = settings.web_token_ttl
# Without a configured key, sessions are invalidated whenever the server restarts.
TOKEN_SECRET = settings.web_secret_key or secrets.token_hex(32)
PBKDF2_ITERATIONS = 390_000
MIN_PASSWORD_LENGTH = 10


# ---------- passwords ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(email) > 256:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    return email


# ---------- one-time tokens (invites) ----------

def new_invite_token() -> tuple[str, str]:
    """Returns (raw token for the link, hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_invite_token(raw)


def hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------- session tokens ----------

def _sign(payload: str) -> str:
    return hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + TOKEN_TTL_SECONDS}"
    return base64.urlsafe_b64encode(f"{payload}:{_sign(payload)}".encode()).decode()


def current_user(
    authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)
) -> AppUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        raw = base64.urlsafe_b64decode(authorization.removeprefix("Bearer ").encode()).decode()
        user_id, expires, signature = raw.split(":")
        user_id_int, expires_at = int(user_id), int(expires)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session")
    if not hmac.compare_digest(signature, _sign(f"{user_id}:{expires}")) or expires_at < time.time():
        raise HTTPException(status_code=401, detail="Session expired")
    # Re-read the user each request so disabling an account or changing a role applies immediately.
    user = db.get(AppUser, user_id_int)
    if not user or user.status != STATUS_ACTIVE:
        raise HTTPException(status_code=401, detail="Account is not active")
    return user


def require_admin(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role not in (ROLE_ADMIN, ROLE_SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_super_admin(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def assignable_roles(actor: AppUser) -> list[str]:
    """Super admins can grant any role; admins can only grant the user role."""
    if actor.role == ROLE_SUPER_ADMIN:
        return [ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN]
    if actor.role == ROLE_ADMIN:
        return [ROLE_USER]
    return []


def ensure_can_manage(actor: AppUser, target: AppUser) -> None:
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="You cannot change your own account")
    if actor.role != ROLE_SUPER_ADMIN and target.role != ROLE_USER:
        raise HTTPException(status_code=403, detail="Only a super admin can manage admins")


def ensure_can_assign(actor: AppUser, role: str) -> None:
    if role not in assignable_roles(actor):
        raise HTTPException(status_code=403, detail=f"You cannot grant the '{role}' role")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- login throttling (per process) ----------

_FAILED_LOGINS: dict[str, deque] = defaultdict(deque)
MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW = 15 * 60


def check_login_throttle(key: str) -> None:
    attempts = _FAILED_LOGINS[key]
    while attempts and attempts[0] < time.time() - FAILED_LOGIN_WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_FAILED_LOGINS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")


def record_failed_login(key: str) -> None:
    _FAILED_LOGINS[key].append(time.time())


def clear_failed_logins(key: str) -> None:
    _FAILED_LOGINS.pop(key, None)
