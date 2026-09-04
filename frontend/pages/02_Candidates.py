import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
import re
from typing import Optional

import streamlit as st
from sqlalchemy.orm import Session

from frontend.db import get_db
from frontend.repository import (
    create_candidate,
    delete_candidate,
    get_candidate,
    get_candidates,
    update_candidate,
)
from gt_linkedin_scraper.models.candidate import Candidate

st.set_page_config(page_title="Candidates", layout="wide")

ALLOWED_TAGS = ["devops", "java", "qa", "freshers", "data_engineer"]


def slugify_name(name: str) -> str:
    value = name.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "candidate"


def save_resume_file(uploaded_file, candidate_name: str) -> Optional[str]:
    if uploaded_file is None:
        return None
    folder_name = slugify_name(candidate_name)
    upload_dir = os.path.join("ResumeUploads", folder_name)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return os.path.relpath(file_path, start="ResumeUploads")


def candidate_form(candidate=None):
    with st.form("candidate_form"):
        name = st.text_input("Name", value=candidate.name if candidate else "")
        number = st.text_input("Number", value=candidate.number if candidate else "")
        subscription = st.text_input("Subscription", value=candidate.subscription if candidate else "")
        is_active = st.checkbox("Is Active", value=candidate.is_active if candidate else True)
        email = st.text_input("Email", value=candidate.email if candidate else "")
        email_password = st.text_input("Email Password", value=candidate.email_password if candidate else "", type="password")
        tag = st.selectbox("Tag", ALLOWED_TAGS, index=ALLOWED_TAGS.index(candidate.tag) if candidate and candidate.tag in ALLOWED_TAGS else 0)
        resume_file = st.file_uploader("Resume", type=["pdf", "docx"])
        email_body = st.text_area("Email Body (HTML)", value=candidate.email_body if candidate else "", height=200)
        submitted = st.form_submit_button("Save")
        if submitted:
            return {
                "name": name,
                "number": number,
                "subscription": subscription,
                "is_active": is_active,
                "email": email,
                "email_password": email_password,
                "tag": tag,
                "resume_file": resume_file,
                "email_body": email_body,
            }
    return None


def render_candidates():
    db: Session = next(get_db())
    try:
        candidates = get_candidates(db)
    finally:
        db.close()

    st.subheader("Candidates")
    if not candidates:
        st.info("No candidates found.")
        return

    for candidate in candidates:
        with st.expander(f"{candidate.name} ({candidate.tag})"):
            st.write(f"**Number:** {candidate.number}")
            st.write(f"**Subscription:** {candidate.subscription}")
            st.write(f"**Active:** {candidate.is_active}")
            st.write(f"**Email:** {candidate.email}")
            st.write(f"**Resume:** {candidate.resume}")
            st.write(f"**Email Body:** {candidate.email_body[:500]}...")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Edit", key=f"edit_{candidate.id}"):
                    st.session_state["edit_candidate_id"] = candidate.id
            with col2:
                if st.button("Delete", key=f"delete_{candidate.id}"):
                    st.session_state["delete_candidate_id"] = candidate.id


st.title("Candidates")

edit_id = st.session_state.get("edit_candidate_id")
delete_id = st.session_state.get("delete_candidate_id")

if delete_id:
    db: Session = next(get_db())
    try:
        candidate = get_candidate(db, delete_id)
        if candidate:
            st.warning(f"Delete {candidate.name}?")
            if st.button("Confirm Delete"):
                delete_candidate(db, delete_id)
                st.session_state.pop("delete_candidate_id", None)
                st.rerun()
            if st.button("Cancel"):
                st.session_state.pop("delete_candidate_id", None)
                st.rerun()
        else:
            st.session_state.pop("delete_candidate_id", None)
            st.rerun()
    finally:
        db.close()

if edit_id:
    db: Session = next(get_db())
    try:
        candidate = get_candidate(db, edit_id)
        if candidate:
            st.subheader("Edit Candidate")
            form_data = candidate_form(candidate)
            if form_data:
                resume_path = save_resume_file(form_data["resume_file"], form_data["name"])
                candidate.name = form_data["name"]
                candidate.number = form_data["number"]
                candidate.subscription = form_data["subscription"]
                candidate.is_active = form_data["is_active"]
                candidate.email = form_data["email"]
                candidate.email_password = form_data["email_password"]
                candidate.tag = form_data["tag"]
                if resume_path:
                    candidate.resume = resume_path
                candidate.email_body = form_data["email_body"]
                update_candidate(db, edit_id, candidate)
                st.session_state.pop("edit_candidate_id", None)
                st.rerun()
        else:
            st.session_state.pop("edit_candidate_id", None)
            st.rerun()
    finally:
        db.close()
else:
    st.subheader("Add Candidate")
    form_data = candidate_form()
    if form_data:
        db: Session = next(get_db())
        try:
            resume_path = save_resume_file(form_data["resume_file"], form_data["name"])
            candidate = Candidate(
                name=form_data["name"],
                number=form_data["number"],
                subscription=form_data["subscription"],
                is_active=form_data["is_active"],
                email=form_data["email"],
                email_password=form_data["email_password"],
                tag=form_data["tag"],
                resume=resume_path,
                email_body=form_data["email_body"],
            )
            create_candidate(db, candidate)
            st.rerun()
        finally:
            db.close()

render_candidates()
