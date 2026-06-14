import streamlit as st
from pathlib import Path

from database import *

IMAGES_DIR = Path(__file__).parent / "images"

st.set_page_config(page_title="CG Progress", page_icon=str(IMAGES_DIR / "logo(89x89).png"), layout="wide")

st.logo(str(IMAGES_DIR / "logo(1048x238)-removed.png"), size="large")

# ── 로그인 게이트 ─────────────────────────────────────────
def _login_page():
    st.title("🔐 로그인이 필요합니다")
    st.button("Microsoft 계정으로 로그인", on_click=st.login, args=("microsoft",),
              type="primary", use_container_width=True)

if not st.user.is_logged_in:
    pg = st.navigation([st.Page(_login_page, title="로그인", default=True)])
    pg.run()
    st.stop()

# ── 사용자 역할 확인 및 session_state 저장 ────────────────
if "role" not in st.session_state:
    st.session_state.role = get_or_create_user(st.user.email, st.user.name)

role = st.session_state.role
ROLE_LABEL = {"admin": "관리자", "editor": "편집자", "viewer": "뷰어"}

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.write(f"**{st.user.name}**")
    st.write(f"{st.user.email}")
    st.caption(ROLE_LABEL.get(role, role))
    st.button("로그아웃", on_click=st.logout, use_container_width=True)

# ── 네비게이션 ────────────────────────────────────────────
pages = [
    st.Page("pages/1_main.py",              title="전체 진척도",  icon=":material/bar_chart_4_bars:",      default=True),
    st.Page("pages/2_functional_test.py",   title="기능 테스트",  icon=":material/developer_board:"),
    st.Page("pages/3_conformal_coating.py", title="컨포멀 코팅",  icon=":material/fragrance:"),
]

if role == "admin":
    pages.append(st.Page("pages/admin.py", title="사용자 관리", icon=":material/manage_accounts:"))

pg = st.navigation(pages)

with st.bottom:
    st.caption("Copyright 2026. JAEBIN KIM All rights reserved.")

pg.run()
