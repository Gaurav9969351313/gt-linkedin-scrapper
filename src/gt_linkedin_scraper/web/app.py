"""FastAPI app behind the invite-only Angular frontend (apps/web).

Run: uvicorn gt_linkedin_scraper.web.app:app --port 8502
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.web.routes import admin, auth, candidates, jobs, tags

app = FastAPI(title="LinkedIn Scraper Web API", version="0.2.0")

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


# Serve the built Angular app (production). In development the Angular dev server
# proxies /api here instead.
static_root = Path(settings.web_static_dir).resolve() if settings.web_static_dir else None

if static_root and static_root.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        requested = (static_root / full_path).resolve()
        if full_path and requested.is_file() and static_root in requested.parents:
            return FileResponse(requested)
        return FileResponse(static_root / "index.html")
