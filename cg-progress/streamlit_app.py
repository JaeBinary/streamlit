from pathlib import Path

import streamlit as st

from constants import ROLE_LABEL
from database import get_or_create_user

IMAGES_DIR = Path(__file__).parent / "images"

st.set_page_config(
    page_title="CG Progress",
    page_icon=str(IMAGES_DIR / "logo(89x89).png"),
    layout="wide",
)
st.logo(str(IMAGES_DIR / "logo(1048x238)-removed.png"), size="large")

# ── 로그인 게이트 ─────────────────────────────────────────
# 공식 문서 권장 패턴: 미로그인 시 로그인 버튼만 그리고 st.stop()으로 중단한다.
# 이렇게 하면 아래 st.navigation(하위 페이지)에 도달조차 못 하므로 비로그인 접근이 차단된다.
# https://docs.streamlit.io/develop/concepts/connections/authentication
# getattr: secrets.toml에 [auth]가 없으면 st.user.is_logged_in 자체가 없으므로 안전하게 False 처리.
if not getattr(st.user, "is_logged_in", False):
    st.title("🔐 로그인이 필요합니다")
    st.button("Microsoft 계정으로 로그인", on_click=st.login, args=("microsoft",),
              type="primary", width="stretch")
    st.stop()

# ── 사용자 역할 확인 및 session_state 저장 ────────────────
if "role" not in st.session_state:
    st.session_state.role = get_or_create_user(st.user.email, st.user.name)

role = st.session_state.role

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.html(f"<h3 style='margin:0'>{st.user.name}</h3>")
    # st.markdown은 GFM 자동 링크로 이메일을 mailto: 링크로 바꾼다.
    # st.html은 마크다운을 거치지 않아 자동 링크 없이 평문으로 표시된다.
    st.html(f"<h5 style='margin:0'>{st.user.email}</h5>")
    st.caption(ROLE_LABEL.get(role, role))
    st.button("로그아웃", on_click=st.logout, width="stretch")

# ── 네비게이션 ────────────────────────────────────────────
# st.navigation에 dict를 넘기면 키가 사이드바의 섹션 머리글이 되어 페이지가 그룹으로 묶인다.
# https://docs.streamlit.io/develop/api-reference/navigation/st.navigation
pages = {
    # 빈 문자열 키는 머리글 없이 렌더링되어 "전체 진척도"가 최상단에 독립 표시된다.
    "": [
        st.Page("pages/1_main.py",              title="전체 진척도",  icon=":material/bar_chart_4_bars:",      default=True),
        st.Page("pages/2_functional_test.py",   title="기능 테스트",  icon=":material/developer_board:"),
        st.Page("pages/3_conformal_coating.py", title="컨포멀 코팅",  icon=":material/fragrance:"),
    ],
}

# 관리자 전용 그룹: admin일 때만 "관리자" 섹션을 통째로 추가해 두 페이지를 함께 노출한다.
if role == "admin":
    pages["관리자"] = [
        st.Page("pages/authorization.py", title="사용자 권한", icon=":material/manage_accounts:"),
        st.Page("pages/verification.py",  title="검수 리스트", icon=":material/verified:"),
    ]

pg = st.navigation(pages)

with st.bottom:
    st.caption("Copyright 2026. JAEBIN KIM All rights reserved.")

pg.run()
