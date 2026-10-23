"""Tag management and scrape-job management: super admin only."""
import pytest
from conftest import auth_headers, make_user

from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.models.extraction import EmailRecord
from gt_linkedin_scraper.models.job import RunLog

JOB = {"keyword": '"Java" AND "Contract"', "scroll_count": 5, "tag": "java", "cron_expression": "31 7 * * *"}
CANDIDATE = {
    "name": "Jane", "number": "1", "subscription": "s", "is_active": "true", "email": "j@x.com",
    "email_password": "pw", "tag": "java", "email_subject": "s", "email_body": "b",
}


@pytest.fixture
def root(client):
    make_user("root@x.com", role="super_admin")
    return auth_headers(client, "root@x.com")


@pytest.mark.parametrize("role", ["admin", "user"])
def test_only_super_admin_can_manage(client, role):
    make_user("p@x.com", role=role)
    h = auth_headers(client, "p@x.com")
    for method, url in [("get", "/api/admin/tags"), ("post", "/api/admin/tags"), ("get", "/api/admin/jobs"),
                        ("post", "/api/admin/jobs"), ("post", "/api/admin/jobs/1/run")]:
        assert getattr(client, method)(url, headers=h).status_code == 403, url
    # ...but everyone can read the active tags for their forms
    assert client.get("/api/tags", headers=h).status_code == 200


# ---------- tags ----------

def test_tag_crud_and_usage(client, root):
    res = client.post("/api/admin/tags", json={"name": "Python_Dev", "label": "Python Dev"}, headers=root)
    assert res.status_code == 201, res.text
    tag = res.json()
    assert tag["name"] == "python_dev" and tag["usage"] == {"jobs": 0, "candidates": 0, "email_records": 0}

    assert client.post("/api/admin/tags", json={"name": "python_dev", "label": "x"}, headers=root).status_code == 409
    assert client.post("/api/admin/tags", json={"name": "bad name!", "label": "x"}, headers=root).status_code == 400

    res = client.put(f"/api/admin/tags/{tag['id']}", json={"label": "Python", "description": "Py roles"}, headers=root)
    assert res.json()["label"] == "Python" and res.json()["description"] == "Py roles"
    assert "python_dev" in [t["name"] for t in client.get("/api/tags", headers=root).json()]

    assert client.delete(f"/api/admin/tags/{tag['id']}", headers=root).status_code == 204


def test_inactive_tag_hidden_from_new_choices_but_kept_on_existing(client, root):
    cand = client.post("/api/candidates", data=CANDIDATE, headers=root).json()
    java = next(t for t in client.get("/api/admin/tags", headers=root).json() if t["name"] == "java")
    assert java["usage"]["candidates"] == 1

    client.put(f"/api/admin/tags/{java['id']}", json={"label": "Java", "is_active": False}, headers=root)
    assert "java" not in [t["name"] for t in client.get("/api/tags", headers=root).json()]
    # can't choose it for a new candidate...
    assert client.post("/api/candidates", data=CANDIDATE, headers=root).status_code == 400
    # ...but the existing candidate can still be saved with it
    assert client.put(f"/api/candidates/{cand['id']}", data=CANDIDATE, headers=root).status_code == 200


def test_tag_in_use_cannot_be_deleted(client, root, prefect_calls):
    client.post("/api/admin/jobs", json=JOB, headers=root)
    java = next(t for t in client.get("/api/admin/tags", headers=root).json() if t["name"] == "java")
    res = client.delete(f"/api/admin/tags/{java['id']}", headers=root)
    assert res.status_code == 409 and "1 job" in res.json()["detail"]


# ---------- jobs ----------

def test_job_lifecycle_syncs_prefect(client, root, prefect_calls):
    res = client.post("/api/admin/jobs", json=JOB, headers=root)
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["status"] == "idle" and job["warning"] is None
    assert prefect_calls[-1] == ("sync", job["id"], "idle")

    res = client.put(f"/api/admin/jobs/{job['id']}", json={**JOB, "cron_expression": "0 9 * * 1-5", "tag": "qa"}, headers=root)
    assert res.json()["cron_expression"] == "0 9 * * 1-5" and res.json()["tag"] == "qa"

    assert client.post(f"/api/admin/jobs/{job['id']}/hold", headers=root).json()["on_hold"] is True
    assert prefect_calls[-1] == ("sync", job["id"], "hold")
    assert client.post(f"/api/admin/jobs/{job['id']}/run", headers=root).status_code == 400  # on hold

    assert client.post(f"/api/admin/jobs/{job['id']}/resume", headers=root).json()["status"] == "idle"
    res = client.post(f"/api/admin/jobs/{job['id']}/run", headers=root)
    assert res.status_code == 202 and res.json()["flow_run_id"] == "flow-run-123"

    assert client.delete(f"/api/admin/jobs/{job['id']}", headers=root).status_code == 200
    assert prefect_calls[-1] == ("delete", job["id"])
    assert client.get("/api/admin/jobs", headers=root).json() == []


@pytest.mark.parametrize(
    "change, message",
    [
        ({"cron_expression": "61 * * * *"}, "Invalid cron"),
        ({"tag": "nope"}, "Unknown or inactive tag"),
        ({"scroll_count": 0}, "Scroll count"),
        ({"keyword": "  "}, "keyword is required"),
    ],
)
def test_job_validation(client, root, prefect_calls, change, message):
    res = client.post("/api/admin/jobs", json={**JOB, **change}, headers=root)
    assert res.status_code == 400 and message in res.json()["detail"]
    assert prefect_calls == []


def test_job_saved_even_if_prefect_is_down(client, root, monkeypatch):
    from gt_linkedin_scraper.scheduler import deployments

    async def down(job):
        raise ConnectionError("prefect down")

    monkeypatch.setattr(deployments, "sync_job", down)
    res = client.post("/api/admin/jobs", json=JOB, headers=root)
    assert res.status_code == 201 and "could not be updated" in res.json()["warning"]
    assert len(client.get("/api/admin/jobs", headers=root).json()) == 1


def test_job_list_shows_last_run_and_email_count(client, root, prefect_calls):
    job = client.post("/api/admin/jobs", json=JOB, headers=root).json()
    with SessionLocal() as db:
        db.add_all([RunLog(job_id=job["id"], status="running"), RunLog(job_id=job["id"], status="completed", records_count=7)])
        db.add_all([EmailRecord(job_id=job["id"], tag="java", email=f"hr{i}@x.com") for i in range(3)])
        db.commit()

    listed = client.get("/api/admin/jobs", headers=root).json()[0]
    assert listed["last_run"]["status"] == "completed" and listed["email_count"] == 3
    runs = client.get(f"/api/admin/jobs/{job['id']}/runs", headers=root).json()
    assert [r["status"] for r in runs] == ["completed", "running"]
