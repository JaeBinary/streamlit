import streamlit as st

# 관리자 전용 페이지. streamlit_app.py에서 admin일 때만 네비게이션에 노출하지만,
# 페이지 단에서도 한 번 더 막아 URL 직접 접근 등 우회 진입을 차단한다(다층 방어).
role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("Verification")
st.caption("검수 대상 항목을 확인하고 관리합니다.")

st.info("준비 중입니다.")
