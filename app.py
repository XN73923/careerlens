"""CareerLens Streamlit application entry point."""

import sqlite3

import streamlit as st

from careerlens.database import initialize_database


st.set_page_config(page_title="CareerLens", page_icon="🔎", layout="centered")

try:
    initialize_database()
except (OSError, sqlite3.Error) as error:
    st.error(f"Could not initialize the local database: {error}")
    st.stop()

st.title("CareerLens")
st.write(
    "CareerLens is an AI-assisted tool for organizing company research and "
    "preparing for selection processes."
)

st.info(
    "AI supports your research and reflection, but it does not make career "
    "decisions for you. You remain responsible for checking sources and making "
    "the final decision."
)

st.subheader("Workflow")
st.markdown(
    "**My Profile** → **Company Research** → **Research Assistant** → "
    "**Selection Preparation**"
)
