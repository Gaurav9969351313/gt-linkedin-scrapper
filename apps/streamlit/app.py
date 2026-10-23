import streamlit as st

from auth import check_auth

st.set_page_config(page_title="LinkedIn Scraper", layout="wide")

if not check_auth():
    st.stop()

st.sidebar.success("Logged in")
st.title("LinkedIn Scraper Frontend")
st.write("Use the sidebar to navigate between pages.")
