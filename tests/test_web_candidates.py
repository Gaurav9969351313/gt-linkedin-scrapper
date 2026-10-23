from pathlib import Path

from conftest import auth_headers, make_user

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.storage.resumes import slugify_name

FORM = {
    "name": "Jane Doe",
    "number": "1",
    "subscription": "gold",
    "is_active": "true",
    "email": "j@x.com",
    "email_password": "pw",
    "tag": "java",
    "email_subject": "Hi",
    "email_body": "<p>b</p>",
}


def add(client, headers, **overrides):
    return client.post("/api/candidates", data={**FORM, **overrides}, headers=headers)


def test_admin_candidate_crud_with_resume(client):
    make_user("adm@x.com", role="admin")
    h = auth_headers(client, "adm@x.com")

    res = client.post(
        "/api/candidates", data=FORM, files={"resume_file": ("cv.pdf", b"%PDF", "application/pdf")}, headers=h
    )
    assert res.status_code == 201, res.text
    created = res.json()
    assert "email_password" not in created
    assert created["owner_email"] == "adm@x.com"
    assert Path(created["resume"]).as_posix() == "jane_doe/cv.pdf"
    assert (Path(settings.resume_upload_dir) / created["resume"]).read_bytes() == b"%PDF"

    # Blank password keeps the stored one.
    res = client.put(f"/api/candidates/{created['id']}", data={**FORM, "email_password": "", "tag": "qa"}, headers=h)
    assert res.status_code == 200 and res.json()["tag"] == "qa"
    with SessionLocal() as db:
        assert db.get(Candidate, created["id"]).email_password == "pw"

    assert len(client.get("/api/candidates?tag=qa", headers=h).json()) == 1
    assert client.delete(f"/api/candidates/{created['id']}", headers=h).status_code == 204
    assert client.get(f"/api/candidates/{created['id']}", headers=h).status_code == 404


def test_admin_can_add_many_and_sees_everyones(client):
    make_user("adm@x.com", role="admin")
    make_user("u@x.com")
    adm = auth_headers(client, "adm@x.com")
    assert add(client, adm, name="A").status_code == 201
    assert add(client, adm, name="B").status_code == 201
    assert add(client, auth_headers(client, "u@x.com"), name="C").status_code == 201

    grid = client.get("/api/candidates", headers=adm).json()
    assert {c["name"]: c["owner_email"] for c in grid} == {"A": "adm@x.com", "B": "adm@x.com", "C": "u@x.com"}


def test_user_can_add_only_one_candidate(client):
    make_user("u@x.com")
    h = auth_headers(client, "u@x.com")

    assert client.get("/api/candidates/mine", headers=h).json() is None
    mine = add(client, h).json()
    assert client.get("/api/candidates/mine", headers=h).json()["id"] == mine["id"]

    res = add(client, h, name="Second")
    assert res.status_code == 409 and "only create one candidature" in res.json()["detail"]

    # ...but can edit their own
    res = client.put(f"/api/candidates/{mine['id']}", data={**FORM, "subject": "x", "tag": "qa"}, headers=h)
    assert res.status_code == 200 and res.json()["tag"] == "qa"


def test_user_cannot_see_grid_or_others_candidates(client):
    make_user("adm@x.com", role="admin")
    make_user("u@x.com")
    other = add(client, auth_headers(client, "adm@x.com")).json()
    h = auth_headers(client, "u@x.com")

    assert client.get("/api/candidates", headers=h).status_code == 403
    assert client.get(f"/api/candidates/{other['id']}", headers=h).status_code == 404
    assert client.put(f"/api/candidates/{other['id']}", data=FORM, headers=h).status_code == 404


def test_user_cannot_delete_even_own_candidate(client):
    make_user("u@x.com")
    h = auth_headers(client, "u@x.com")
    mine = add(client, h).json()
    assert client.delete(f"/api/candidates/{mine['id']}", headers=h).status_code == 403


def test_candidate_validation(client):
    make_user("adm@x.com", role="admin")
    h = auth_headers(client, "adm@x.com")
    assert add(client, h, tag="bad").status_code == 400
    bad_file = {"resume_file": ("cv.exe", b"x", "application/octet-stream")}
    assert client.post("/api/candidates", data=FORM, files=bad_file, headers=h).status_code == 400


def test_dashboard_and_tags(client):
    make_user("u@x.com")
    h = auth_headers(client, "u@x.com")
    assert client.get("/api/dashboard/stats", headers=h).json() == {"total": 0, "tag_count": 0, "by_tag": [], "by_date": []}
    assert [t["name"] for t in client.get("/api/tags", headers=h).json()] == ["devops", "java", "qa", "freshers", "data_engineer"]


def test_slugify_name():
    assert slugify_name("Gaurav Y. Talele") == "gaurav_y_talele"
    assert slugify_name("***") == "candidate"
