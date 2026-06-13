import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Hello", page_icon="👋")

st.write("# Welcome to Streamlit! 👋")
st.sidebar.success("Select a demo above.")

st.markdown((Path(__file__).parent / "content/hello.md").read_text(encoding="utf-8"))
