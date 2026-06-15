import streamlit as st

from database import load_users, update_role

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

ROLE_LABEL = {"admin": "🔴 관리자", "editor": "🟡 편집자", "viewer": "🟢 뷰어"}

st.title("👥 사용자 관리")

users_df = load_users()
st.dataframe(users_df, width="stretch", hide_index=True)

st.divider()
# 폼 대신 일반 위젯 + 버튼 사용 (Enter 제출이 필요 없는 화면).
# 멀티페이지 전환 시 폼이 'Missing Submit Button'으로 깜빡이는 현상을 줄이기 위함.
target_email = st.selectbox("변경할 계정", users_df["email"].tolist())
new_role = st.selectbox("새 역할", list(ROLE_LABEL.keys()), format_func=ROLE_LABEL.get)
if st.button("역할 변경", type="primary"):
    update_role(target_email, new_role)
    # 위 사용자 목록을 갱신하려면 rerun이 필요한데, rerun은 st.success를 즉시 지운다.
    # rerun 후에도 유지되는 st.toast로 결과와 '재로그인 후 적용' 안내를 함께 표시한다.
    st.toast(f"{target_email} → {ROLE_LABEL[new_role]} · 대상자 재로그인 후 적용", icon="✅")
    st.rerun()
