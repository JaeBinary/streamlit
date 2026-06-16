import streamlit as st

from constants import ROLE_LABEL
from database import load_users, update_user

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("Authorization")

EDITOR_KEY = "users_editor"
users_df = load_users()

# 표에서 바로 name·role을 편집한다. email·가입일은 잠그고(disabled),
# role은 정해진 값만 고르도록 SelectboxColumn으로 제한한다. num_rows="fixed"로 행 추가/삭제 금지.
# https://docs.streamlit.io/develop/api-reference/data/st.data_editor
edited = st.data_editor(
    users_df,
    width="stretch",
    hide_index=True,
    key=EDITOR_KEY,
    num_rows="fixed",
    column_config={
        "email": st.column_config.TextColumn("email", disabled=True),
        "name": st.column_config.TextColumn("name", required=True),
        "role": st.column_config.SelectboxColumn("role", options=list(ROLE_LABEL), required=True),
        "date_first_registered": st.column_config.TextColumn("date_first_registered", disabled=True),
    },
)

# 변경분만 추려 저장한다. email(PK)을 인덱스로 맞춰 (name, role)이 달라진 행만 모은다.
orig = users_df.set_index("email")
new = edited.set_index("email")
changed = [
    email for email in new.index
    if (new.at[email, "name"], new.at[email, "role"]) != (orig.at[email, "name"], orig.at[email, "role"])
]

# 마지막 관리자 보호: 저장 결과 admin이 0명이 되는 변경은 막는다.
no_admin_left = (edited["role"] == "admin").sum() == 0

st.divider()
if st.button("변경사항 저장", type="primary", width="stretch", disabled=not changed):
    if no_admin_left:
        st.error("관리자(admin)는 최소 1명이 필요합니다. 변경사항을 저장하지 않았습니다.")
    else:
        for email in changed:
            update_user(email, new.at[email, "name"], new.at[email, "role"])
        # 다음 실행에서 갱신된 목록으로 에디터를 다시 초기화하도록 편집 상태를 비운다.
        # rerun 후에도 유지되는 st.toast로 결과와 '재로그인 후 적용' 안내를 함께 표시한다.
        st.session_state.pop(EDITOR_KEY, None)
        st.toast(f"{len(changed)}건 저장 · 대상자 재로그인 후 적용", icon="✅")
        st.rerun()
