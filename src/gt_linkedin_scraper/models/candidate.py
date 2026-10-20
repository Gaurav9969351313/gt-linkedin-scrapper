from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func, text
from sqlalchemy.sql import func as sql_func

from gt_linkedin_scraper.core.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    number = Column(String(64), nullable=False)
    subscription = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("false"))
    email = Column(String(256), nullable=False)
    email_password = Column(String(256), nullable=False)
    resume = Column(String(512), nullable=True)
    email_body = Column(Text, nullable=False)
    email_subject = Column(String(512), nullable=False)
    tag = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=sql_func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sql_func.now(), onupdate=sql_func.now(), nullable=False)
