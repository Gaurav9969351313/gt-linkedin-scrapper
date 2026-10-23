from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.sql import func as sql_func

from gt_linkedin_scraper.core.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    number = Column(String(64), nullable=False)
    subscription = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    email = Column(String(256), nullable=False)
    email_password = Column(String(256), nullable=False)
    resume = Column(String(512), nullable=True)
    email_body = Column(Text, nullable=False)
    email_subject = Column(String(512), nullable=False)
    tag = Column(String(64), nullable=False)
    # Web-app account that created the candidate. A "user" may own at most one;
    # NULL for candidates added through Streamlit or scripts.
    owner_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=sql_func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sql_func.now(), onupdate=sql_func.now(), nullable=False)
