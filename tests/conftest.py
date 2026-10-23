"""Test configuration: point the app at a throwaway SQLite database before anything imports it."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="gt-tests-"))
_db = (_tmp / "test.db").as_posix()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{_db}"
os.environ["RESUME_UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["WEB_STATIC_DIR"] = ""
os.environ["SMTP_USER"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import gt_linkedin_scraper.models  # noqa: E402,F401
from gt_linkedin_scraper.core.database import Base  # noqa: E402
from gt_linkedin_scraper.core.sync_database import SessionLocal, engine  # noqa: E402
from gt_linkedin_scraper.models.app_user import AppUser  # noqa: E402
from gt_linkedin_scraper.models.tag import DEFAULT_TAGS, Tag  # noqa: E402
from gt_linkedin_scraper.web import security  # noqa: E402
from gt_linkedin_scraper.web.app import app  # noqa: E402

Base.metadata.create_all(engine)

PASSWORD = "test-password-123"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(Tag.__table__.insert(), [{"name": n, "label": label} for n, label in DEFAULT_TAGS])
    security._FAILED_LOGINS.clear()
    yield


@pytest.fixture
def prefect_calls(monkeypatch):
    """Replaces Prefect calls with recorders, so job tests don't need a Prefect server."""
    calls: list[tuple] = []
    from gt_linkedin_scraper.scheduler import deployments

    async def sync_job(job):
        calls.append(("sync", job.id, job.status))

    async def delete_job_deployment(job_id):
        calls.append(("delete", job_id))

    async def run_job_now(job_id, run_name=None):
        calls.append(("run", job_id))
        return "flow-run-123"

    monkeypatch.setattr(deployments, "sync_job", sync_job)
    monkeypatch.setattr(deployments, "delete_job_deployment", delete_job_deployment)
    monkeypatch.setattr(deployments, "run_job_now", run_job_now)
    return calls


@pytest.fixture
def sent_emails(monkeypatch):
    """Captures outgoing email instead of sending it."""
    sent: list[tuple[list[str], str]] = []

    def fake_send(to, subject, text):
        sent.append((to, subject))
        return True

    for module in ("invitations", "routes.auth", "routes.admin"):
        monkeypatch.setattr(f"gt_linkedin_scraper.web.{module}.send_email", fake_send)
    return sent


@pytest.fixture
def client(sent_emails):
    return TestClient(app)


def make_user(email: str, role: str = "user", status: str = "active", name: str = "Test") -> AppUser:
    with SessionLocal() as db:
        user = AppUser(
            email=email, name=name, password_hash=security.hash_password(PASSWORD), role=role, status=status
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth_headers(client: TestClient, email: str) -> dict:
    res = login(client, email)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}
