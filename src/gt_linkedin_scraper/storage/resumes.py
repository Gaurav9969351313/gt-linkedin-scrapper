"""Candidate resume files, shared by the Streamlit app, the web API, CLI scripts and the email flow.

Resumes live under settings.resume_upload_dir/<slugified candidate name>/<file>, and the
database stores the path relative to settings.resume_upload_dir.
"""
import os
import re
from pathlib import Path
from typing import Optional

from gt_linkedin_scraper.core.config import settings

ALLOWED_RESUME_SUFFIXES = {".pdf", ".docx"}


def slugify_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return value or "candidate"


def save_resume(content: bytes, filename: str, candidate_name: str) -> str:
    """Writes the file and returns the path to store on the candidate."""
    upload_root = Path(settings.resume_upload_dir)
    upload_dir = upload_root / slugify_name(candidate_name)
    upload_dir.mkdir(parents=True, exist_ok=True)
    # Keep only the base name so a crafted filename can't escape the upload directory.
    file_path = upload_dir / Path(filename).name
    file_path.write_bytes(content)
    return os.path.relpath(file_path, start=upload_root)


def resolve_resume(stored_path: str) -> Optional[Path]:
    """Absolute path of a stored resume, or None if the file is missing."""
    path = Path(settings.resume_upload_dir) / stored_path
    return path if path.exists() else None
