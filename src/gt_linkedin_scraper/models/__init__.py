# Import every model so Base.metadata is complete for Alembic and init_db.
from gt_linkedin_scraper.models.app_user import AppInvitation, AppUser
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.models.enums import JobStatus
from gt_linkedin_scraper.models.extraction import EmailRecord, PostRecord
from gt_linkedin_scraper.models.job import Job, RunLog
from gt_linkedin_scraper.models.tag import Tag

__all__ = [
    "AppInvitation",
    "AppUser",
    "Candidate",
    "EmailRecord",
    "Job",
    "JobStatus",
    "PostRecord",
    "RunLog",
    "Tag",
]
