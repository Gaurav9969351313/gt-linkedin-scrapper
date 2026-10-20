from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func
from gt_linkedin_scraper.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(512), nullable=False)
    scroll_count = Column(Integer, nullable=False, default=10)
    tag = Column(String(64), nullable=False, default="java")
    cron_expression = Column(String(128), nullable=False)
    status = Column(String(64), nullable=False, default="idle")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('idle','running','completed','error','hold','deleted')", name="ck_job_status"),
        CheckConstraint("scroll_count > 0", name="ck_scroll_count_positive"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_tag", "tag"),
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False)
    status = Column(String(64), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(1024), nullable=True)
    records_count = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_run_logs_job_id", "job_id"),
        Index("ix_run_logs_started_at", "started_at"),
    )
