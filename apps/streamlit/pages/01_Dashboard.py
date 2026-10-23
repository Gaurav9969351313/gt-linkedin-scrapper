import streamlit as st

from auth import check_auth
from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.storage.sync_repository import get_email_stats

st.set_page_config(page_title="Dashboard", layout="wide")

if not check_auth():
    st.stop()

with SessionLocal() as db:
    total, tag_count, tags, dates = get_email_stats(db)

st.title("Dashboard")
st.metric("Total Email Records", total or 0)
st.metric("Total Tags", tag_count or 0)

if tags:
    st.subheader("Emails by Tag")
    tag_data = {row.tag: row.count for row in tags}
    st.bar_chart(tag_data)
    st.subheader("Tag Counts")
    st.table({"Tag": [row.tag for row in tags], "Count": [row.count for row in tags]})
else:
    st.info("No tag data available yet.")

if dates:
    st.subheader("Emails by Date")
    date_data = {str(row.date): row.count for row in dates}
    st.bar_chart(date_data)
else:
    st.info("No date data available yet.")
