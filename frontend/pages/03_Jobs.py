import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os

import httpx
import streamlit as st
from sqlalchemy.orm import Session

from frontend.db import get_db
from frontend.repository import get_jobs

st.set_page_config(page_title="Jobs", layout="wide")

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.title("Jobs")

st.subheader("Add Job")
with st.form("job_form", clear_on_submit=True):
    keyword = st.text_input("Search Keyword", placeholder='"Java" AND "Contract"')
    tag = st.text_input("Tag", placeholder="java")
    scroll_count = st.number_input("Scroll Count", min_value=1, value=10, step=1)
    cron = st.text_input("Cron Schedule (Asia/Kolkata)", value="31 7 * * *", help="minute hour day month weekday")
    submitted = st.form_submit_button("Add Job")

if submitted:
    if not keyword.strip():
        st.error("Search keyword is required.")
    elif not tag.strip():
        st.error("Tag is required.")
    else:
        try:
            response = httpx.post(
                f"{API_URL}/jobs/",
                json={"keyword": keyword, "tag": tag, "scroll_count": int(scroll_count), "cron": cron},
                timeout=30,
            )
        except httpx.HTTPError as exc:
            st.error(f"Could not reach the API at {API_URL}: {exc}")
        else:
            if response.status_code == 200:
                job = response.json()
                st.success(f"Job {job['id']} added. Prefect deployment: scrape-job-{job['id']}")
            elif response.status_code == 422:
                errors = response.json().get("detail", [])
                messages = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in errors]
                st.error("Invalid job: " + "; ".join(messages))
            else:
                st.error(response.json().get("detail", response.text))

st.subheader("Existing Jobs")
db: Session = next(get_db())
try:
    jobs = get_jobs(db)
finally:
    db.close()

if not jobs:
    st.info("No jobs found.")
else:
    st.dataframe(
        [
            {
                "ID": j.id,
                "Keyword": j.keyword,
                "Tag": j.tag,
                "Scroll Count": j.scroll_count,
                "Cron": j.cron_expression,
                "Status": j.status,
                "Prefect Deployment": f"scrape-job-{j.id}",
            }
            for j in jobs
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Delete Job")
    jobs_by_id = {j.id: j for j in jobs}
    delete_id = st.selectbox(
        "Job",
        list(jobs_by_id),
        format_func=lambda i: f"{i} - {jobs_by_id[i].keyword} ({jobs_by_id[i].tag})",
    )
    if st.button("Delete Job"):
        st.session_state["delete_job_id"] = delete_id

    pending_id = st.session_state.get("delete_job_id")
    if pending_id in jobs_by_id:
        st.warning(
            f"Delete job {pending_id} and remove its Prefect deployment scrape-job-{pending_id}? "
            "Its scraped emails and posts stay in the database."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm Delete"):
                st.session_state.pop("delete_job_id", None)
                try:
                    response = httpx.delete(f"{API_URL}/jobs/{pending_id}", timeout=30)
                except httpx.HTTPError as exc:
                    st.error(f"Could not reach the API at {API_URL}: {exc}")
                else:
                    if response.status_code == 200:
                        st.rerun()
                    st.error(response.json().get("detail", response.text))
        with col2:
            if st.button("Cancel"):
                st.session_state.pop("delete_job_id", None)
                st.rerun()
