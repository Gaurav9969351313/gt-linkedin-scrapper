"""Smoke tests for the Streamlit app in apps/streamlit (imports, auth gate, page rendering)."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from gt_linkedin_scraper.core.sync_database import SessionLocal  # noqa: E402
from gt_linkedin_scraper.models.candidate import Candidate  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1] / "apps" / "streamlit"
# `streamlit run app.py` puts the app folder on sys.path so pages can `import auth`.
sys.path.insert(0, str(APP_DIR))

SECRETS = {"auth": {"username": "admin", "password": "secret"}}


def run(script: str, authenticated: bool) -> AppTest:
    at = AppTest.from_file(str(APP_DIR / script), default_timeout=30)
    at.secrets.update(SECRETS)
    if authenticated:
        at.session_state["authenticated"] = True
    return at.run()


@pytest.mark.parametrize("script", ["app.py", "pages/01_Dashboard.py", "pages/02_Candidates.py"])
def test_every_page_requires_login(script):
    at = run(script, authenticated=False)
    assert not at.exception
    assert at.title[0].value == "Login"


def test_login_with_secrets():
    at = run("app.py", authenticated=False)
    at.text_input[0].input("admin")
    at.text_input[1].input("secret")
    at.button[0].click().run()
    assert at.session_state["authenticated"] is True
    assert at.title[0].value == "LinkedIn Scraper Frontend"


def test_dashboard_renders():
    at = run("pages/01_Dashboard.py", authenticated=True)
    assert not at.exception
    assert at.title[0].value == "Dashboard"


def test_candidates_page_lists_candidates():
    with SessionLocal() as db:
        db.add(Candidate(name="Jane Doe", number="1", subscription="gold", is_active=True, email="j@x.com",
                         email_password="pw", email_body="<p>b</p>", email_subject="Hi", tag="java"))
        db.commit()
    at = run("pages/02_Candidates.py", authenticated=True)
    assert not at.exception
    assert any("Jane Doe" in e.label for e in at.expander)
