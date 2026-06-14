import streamlit as st

role = st.session_state.get("role", "viewer")

st.title("CG Progress")
st.caption('CG PCB 5종에 대한 "사전작업 진척도"를 표시합니다.')
