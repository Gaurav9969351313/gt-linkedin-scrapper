from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from gt_linkedin_scraper.core.database import Base


class EmailRecord(Base):
    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(64), nullable=False, default="java")
    email = Column(String(256), nullable=False)
    source_post_content = Column(Text, nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_email_records_job_id", "job_id"),
        Index("ix_email_records_scraped_at", "scraped_at"),
        Index("ix_email_records_tag", "tag"),
    )


class PostRecord(Base):
    __tablename__ = "post_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    username = Column(String(256), nullable=True)
    content = Column(Text, nullable=True)
    emails_found = Column(String(512), nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_post_records_job_id", "job_id"),
        Index("ix_post_records_scraped_at", "scraped_at"),
    )
