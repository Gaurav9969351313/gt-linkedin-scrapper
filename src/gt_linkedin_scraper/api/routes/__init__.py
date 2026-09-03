from fastapi import APIRouter
from gt_linkedin_scraper.api.routes import jobs, extractions, triggers

api_router = APIRouter()
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(extractions.router, prefix="/extractions", tags=["extractions"])
api_router.include_router(triggers.router, prefix="/trigger", tags=["triggers"])
