"""Step-by-step run logging for scrape jobs, and Prefect run states.

The browser and LinkedIn are replaced by fakes; everything else (run_job, the database,
RunSteps, the Prefect flow) is real.
"""
import asyncio
import logging

import pytest
from conftest import make_user  # noqa: F401  (ensures conftest's DB setup is loaded)

from gt_linkedin_scraper.core.database import async_session_factory
from gt_linkedin_scraper.core.exceptions import LoginFailed
from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.models.extraction import EmailRecord
from gt_linkedin_scraper.models.job import Job, RunLog
from gt_linkedin_scraper.scheduler import tasks
from gt_linkedin_scraper.scheduler.progress import RunSteps

HTML = "<div>Hiring! Send CVs to hr1@acme.com or jobs@beta.io</div><p>also hr1@acme.com</p>"


class FakePool:
    async def start(self):
        pass

    async def new_context(self):
        return FakeContext()

    async def stop(self):
        pass


class FakeContext:
    async def new_page(self):
        return object()

    async def close(self):
        pass


def fake_crawler(login_error=None):
    class FakeCrawler:
        def __init__(self, context):
            pass

        async def ensure_login(self, page):
            if login_error:
                raise login_error

        async def navigate_to_search(self, page, keyword):
            pass

        async def scroll_and_collect(self, page, scroll_count, progress=None):
            for i in range(1, scroll_count + 1):
                progress(f"Scroll {i}/{scroll_count}: page is 10 KB, 2 unique email(s) visible so far")
            return HTML

    return FakeCrawler


@pytest.fixture
def job(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks, "BrowserPool", FakePool)
    monkeypatch.setattr(tasks.settings, "extract_dir", str(tmp_path / "extract"))
    with SessionLocal() as db:
        j = Job(keyword='"Java" AND "Contract"', scroll_count=2, tag="java", cron_expression="31 7 * * *", status="idle")
        db.add(j)
        db.commit()
        return j.id


def run(job_id):
    async def main():
        async with async_session_factory() as db:
            return await tasks.run_job(job_id, db)

    return asyncio.run(main())


def log_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "gt_linkedin_scraper.runs"]


def test_successful_run_logs_every_step(job, monkeypatch, caplog):
    monkeypatch.setattr(tasks, "LinkedInCrawler", fake_crawler())
    caplog.set_level(logging.INFO)

    result = run(job)

    assert result == {"job_id": job, "status": "completed", "emails": 2, "posts": result["posts"], "error": None}
    lines = log_lines(caplog)
    started = [line for line in lines if line.startswith("▶ Step")]
    assert [line.split(":")[0] for line in started] == [f"▶ Step {i}/8" for i in range(1, 9)]
    assert sum(line.startswith("✓ Step") for line in lines) == 8
    assert any("Scroll 2/2" in line for line in lines)
    assert any("Emails: hr1@acme.com, jobs@beta.io" in line for line in lines)
    assert any("Emails CSV:" in line for line in lines)
    assert lines[-1].startswith("══ Scrape job #") and "finished" in lines[-1]

    with SessionLocal() as db:
        assert db.query(EmailRecord).filter_by(job_id=job).count() == 2
        assert [r.status for r in db.query(RunLog).filter_by(job_id=job).order_by(RunLog.id)] == ["running", "completed"]
        assert db.get(Job, job).status == "completed"


def test_login_failure_is_logged_with_a_hint_and_recorded(job, monkeypatch, caplog):
    monkeypatch.setattr(tasks, "LinkedInCrawler", fake_crawler(LoginFailed("LinkedIn rejected the login: Wrong password")))
    caplog.set_level(logging.INFO)

    result = run(job)

    assert result["status"] == "error" and "Wrong password" in result["error"]
    lines = log_lines(caplog)
    assert any(line.startswith("✗ Step 3/8 failed") and "Log in to LinkedIn" in line for line in lines)
    assert any("What to do: Check LINKEDIN_USERNAME" in line for line in lines)
    assert "FAILED" in lines[-1]
    with SessionLocal() as db:
        assert db.get(Job, job).status == "error"
        last = db.query(RunLog).filter_by(job_id=job).order_by(RunLog.id.desc()).first()
        assert last.status == "error" and "Wrong password" in last.error_message
        assert db.query(EmailRecord).filter_by(job_id=job).count() == 0


def test_job_on_hold_is_skipped(job, monkeypatch, caplog):
    with SessionLocal() as db:
        db.get(Job, job).status = "hold"
        db.commit()
    caplog.set_level(logging.INFO)
    assert run(job)["status"] == "skipped"
    assert any("Skipping remaining steps: the job is on hold" in line for line in log_lines(caplog))


def test_missing_job_fails_cleanly(caplog):
    caplog.set_level(logging.INFO)
    result = run(999_999)
    assert result["status"] == "error" and "does not exist" in result["error"]


def test_report_markdown():
    steps = RunSteps("Scrape job #1", total=2, logger=logging.getLogger("test"))
    with steps.step("First"):
        pass
    with pytest.raises(RuntimeError):
        with steps.step("Second"):
            raise RuntimeError("boom | pipe")
    steps.fact("Emails found", 3)
    steps.finish("broke", ok=False)
    md = steps.markdown()
    assert "| **Result** | ❌ broke |" in md
    assert "| 1 | First | ✅ |" in md
    assert "❌ boom / pipe" in md  # pipes escaped so the table stays intact


def test_prefect_flow_state_reflects_job_result(monkeypatch):
    """A failed scrape must show as Failed in Prefect, not Completed."""
    from prefect.testing.utilities import prefect_test_harness

    from gt_linkedin_scraper.scheduler import flows

    async def fake_run_job(job_id, db):
        if job_id == 1:
            return {"job_id": 1, "status": "completed", "emails": 2, "posts": 0, "error": None}
        return {"job_id": job_id, "status": "error", "emails": 0, "posts": 0, "error": "LoginFailed: nope"}

    monkeypatch.setattr(flows, "run_job", fake_run_job)
    with prefect_test_harness():
        ok = asyncio.run(flows.scrape_single_flow(job_id=1, return_state=True))
        bad = asyncio.run(flows.scrape_single_flow(job_id=2, return_state=True))
    assert ok.is_completed()
    assert bad.is_failed() and "LoginFailed: nope" in bad.message


def test_scraper_info_logs_are_not_filtered_out():
    """Prefect's extra-logger handler only receives what our logger lets through; without an
    explicit level it inherits WARNING and every INFO step from the crawler is dropped."""
    import gt_linkedin_scraper.scheduler.flows  # noqa: F401

    for name in ("gt_linkedin_scraper.crawler.linkedin", "gt_linkedin_scraper.runs"):
        assert logging.getLogger(name).isEnabledFor(logging.INFO), name
