from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func as sql_func

from gt_linkedin_scraper.core.database import Base

# Roles for the invite-only web app (apps/web + gt_linkedin_scraper.web).
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_USER)

# Account lifecycle. Only "active" accounts can log in.
STATUS_PENDING = "pending"    # requested access, waiting for an admin
STATUS_ACTIVE = "active"
STATUS_REJECTED = "rejected"  # access request denied
STATUS_DISABLED = "disabled"  # access revoked by an admin
STATUSES = (STATUS_PENDING, STATUS_ACTIVE, STATUS_REJECTED, STATUS_DISABLED)


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(256), nullable=False, unique=True, index=True)
    name = Column(String(256), nullable=False)
    password_hash = Column(String(512), nullable=False)
    role = Column(String(32), nullable=False, server_default=ROLE_USER)
    status = Column(String(32), nullable=False, server_default=STATUS_PENDING, index=True)
    request_reason = Column(Text, nullable=True)
    invited_by_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sql_func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sql_func.now(), onupdate=sql_func.now(), nullable=False)


class AppInvitation(Base):
    __tablename__ = "app_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(256), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    # Only a SHA-256 of the invite token is stored; the raw token lives in the invite link.
    token_hash = Column(String(64), nullable=False, unique=True)
    invited_by_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sql_func.now(), nullable=False)
