import streamlit as st


def check_auth() -> bool:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.title("Login")
    secrets = st.secrets.get("auth", {})
    username = st.text_input("Username", value="")
    password = st.text_input("Password", type="password", value="")

    if st.button("Login"):
        if username and password and username == secrets.get("username") and password == secrets.get("password"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password")
    return False
