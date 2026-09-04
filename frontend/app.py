import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

st.set_page_config(page_title="LinkedIn Scraper", layout="wide")

from frontend.auth import check_auth

if not check_auth():
    st.stop()

st.sidebar.success("Logged in")
st.title("LinkedIn Scraper Frontend")
st.write("Use the sidebar to navigate between pages.")
