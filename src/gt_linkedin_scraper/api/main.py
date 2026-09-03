from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from gt_linkedin_scraper.core.database import init_db, close_db
from gt_linkedin_scraper.core.logging import setup_logging
from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.scheduler.deployer import run_deployer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.log_format)
    await init_db()
    logger.info("Database initialized")
    try:
        await run_deployer()
        logger.info("Prefect deployer reconciled")
    except Exception as exc:
        logger.error("Deployer failed", exc_info=exc)
    yield
    await close_db()


from gt_linkedin_scraper.api.routes import api_router

app = FastAPI(title="LinkedIn Job Scraper", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
