import streamlit as st

from database import *

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

ROLE_LABEL = {"admin": "🔴 관리자", "editor": "🟡 편집자", "viewer": "🟢 뷰어"}

st.title("👥 사용자 관리")

users_df = load_users()
st.dataframe(users_df, use_container_width=True, hide_index=True)

st.divider()
with st.form("role_form"):
    target_email = st.selectbox("변경할 계정", users_df["email"].tolist())
    new_role = st.selectbox("새 역할", list(ROLE_LABEL.keys()), format_func=ROLE_LABEL.get)
    if st.form_submit_button("역할 변경", type="primary"):
        update_role(target_email, new_role)
        st.success(f"{target_email} → {ROLE_LABEL[new_role]}")
        st.rerun()
