from pathlib import Path

import streamlit as st

from constants import ROLE_COLOR, ROLE_ICON, ROLE_LABEL
from database import get_or_create_user

IMAGES_DIR = Path(__file__).parent / "images"

st.set_page_config(
    page_title="CG Progress",
    page_icon=str(IMAGES_DIR / "logo(89x89).png"),
    layout="wide",
)
st.logo(str(IMAGES_DIR / "logo(1048x238)-removed.png"), size="large")

# ── 로그인 게이트 ─────────────────────────────────────────
# 공식 문서 권장 패턴: 미로그인 시 로그인 화면만 그리고 st.stop()으로 중단한다.
# 이렇게 하면 아래 st.navigation(하위 페이지)에 도달조차 못 하므로 비로그인 접근이 차단된다.
# https://docs.streamlit.io/develop/concepts/connections/authentication
# getattr: secrets.toml에 [auth]가 없으면 st.user.is_logged_in 자체가 없으므로 안전하게 False 처리.
if not getattr(st.user, "is_logged_in", False):
    # layout="wide"라 본문이 가로로 꽉 차므로, 컬럼으로 가운데 좁은 영역을 만들어 로그인 영역을 중앙 배치한다.
    # https://docs.streamlit.io/develop/api-reference/layout/st.columns
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        # 어두운 와이드 제품 렌더를 히어로로 맨 위에 둔다 — 카드 테두리 없이 이미지 자체가 시선 앵커.
        st.image(str(IMAGES_DIR / "Orica-Webgen-200-Mining-Enclosure-Design-Render-04.png"), width="stretch")
        # 제목·부제는 히어로 아래에 가운데 정렬로 통일 — 짧은 인라인 스타일만 사용.
        st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>CGPS</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Current Generator Progress System</p>", unsafe_allow_html=True)
        st.divider()
        # 로그인 동작은 기존과 동일(공식 권장 패턴). 아이콘만 추가.
        st.button("Microsoft 계정으로 로그인", on_click=st.login, args=("microsoft",),
                  icon=":material/login:", type="primary", width="stretch")
    st.stop()

# ── 저작권 푸터 ───────────────────────────────────────────
# st.bottom은 호출 위치와 무관하게 화면 맨 아래에 고정 렌더되지만, 게이트의 st.stop() 아래에 두면
# 로그인 화면에서는 이 코드에 도달하지 못해 푸터가 안 보이고, 로그인 후 화면에서만 노출된다.
# https://docs.streamlit.io/develop/api-reference/layout/st.bottom
with st.bottom:
    st.caption("Copyright 2026. JAEBIN KIM All rights reserved.")

# ── 사용자 역할 확인 및 session_state 저장 ────────────────
if "role" not in st.session_state:
    st.session_state.role = get_or_create_user(st.user.oid, st.user.email, st.user.name)

role = st.session_state.role

# ── 사이드바: 사용자 정보(컴팩트) ─────────────────────────
# 팝오버 트리거(클릭 전)에 아바타·사용자명·권한을 노출하고, 클릭하면 이메일·로그아웃이 나온다.
# 버튼/팝오버 label은 배지·색상 디렉티브를 지원하지 않으므로(굵게/링크 등만) 권한은 텍스트로 두고,
# 아바타 아이콘은 label이 아닌 icon 파라미터로 넣는다.
# https://docs.streamlit.io/develop/api-reference/widgets/st.button
with st.sidebar:
    label = ROLE_LABEL.get(role, role)
    with st.popover(f"**{st.user.name}**",
                    icon=ROLE_ICON.get(role, ":material/account_circle:"), width="stretch"):
        # 팝오버 내용은 마크다운이라 배지 렌더가 가능하다(트리거 label은 배지 미지원).
        st.markdown(f":{ROLE_COLOR.get(role, 'gray')}-badge[{label}]")
        st.caption(st.user.email)
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
        st.Page("pages/authorization.py", title="사용자 권한", icon=":material/admin_panel_settings:"),
        st.Page("pages/verification.py",  title="검수 리스트", icon=":material/verified:"),
    ]

pg = st.navigation(pages)
pg.run()
