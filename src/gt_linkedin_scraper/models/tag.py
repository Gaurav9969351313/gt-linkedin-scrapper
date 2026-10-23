from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.sql import func

from gt_linkedin_scraper.core.database import Base

# Seeded into an empty database (and by the migration that introduced this table).
DEFAULT_TAGS = [
    ("devops", "DevOps"),
    ("java", "Java"),
    ("qa", "QA"),
    ("freshers", "Freshers"),
    ("data_engineer", "Data Engineer"),
]

TAG_NAME_PATTERN = r"^[a-z0-9][a-z0-9_]{0,63}$"


class Tag(Base):
    """A category shared by scrape jobs, the email records they find, and candidates.

    `name` is the stable key stored on jobs/candidates/email_records, so it can't be renamed;
    `label` is what people see.
    """

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    label = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    # Inactive tags stay on existing jobs/candidates but can't be chosen for new ones.
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
