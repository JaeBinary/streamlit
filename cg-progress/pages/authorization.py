import streamlit as st

from constants import ROLE_LABEL, USER_STATUS
from database import load_users, update_user

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("Authorization")
st.caption('사용자의 "권한 관리" 진행합니다.')

users_df = load_users()
counts = users_df["role"].value_counts()

# ── 편집 패널 ─────────────────────────────────────────────
# 표는 읽기 전용으로 두고, 편집은 이 패널에서만 한다. name은 중복될 수 있으므로
# 드롭박스는 PK인 email을 값으로 쓰고 format_func로 name을 보여준다.
name_by_email = dict(zip(users_df["email"], users_df["name"]))
sel_email = st.selectbox(
    "사용자 선택",
    options=users_df["email"].tolist(),
    format_func=lambda e: f"{name_by_email[e]} ({e})",
)
target = users_df[users_df["email"] == sel_email].iloc[0]

with st.form("edit_user"):
    new_name = st.text_input("이름", value=target["name"])
    new_role = st.selectbox(
        "권한", options=list(ROLE_LABEL),
        index=list(ROLE_LABEL).index(target["role"]) if target["role"] in ROLE_LABEL else 0,
        format_func=ROLE_LABEL.get,
    )
    new_status = st.selectbox(
        "상태", options=USER_STATUS,
        index=USER_STATUS.index(target["status"]) if target["status"] in USER_STATUS else 0,
    )
    submitted = st.form_submit_button("저장", type="primary", width="stretch")

if submitted:
    changed = (new_name, new_role, new_status) != (target["name"], target["role"], target["status"])
    # 마지막 관리자 보호: 이 변경을 적용했을 때 admin이 0명이 되면 막는다.
    admins_after = int(counts.get("admin", 0)) - (target["role"] == "admin") + (new_role == "admin")
    if not changed:
        st.toast("변경된 내용이 없습니다.", icon="ℹ️")
    elif admins_after == 0:
        st.error("관리자(admin)는 최소 1명이 필요합니다. 변경사항을 저장하지 않았습니다.")
    else:
        update_user(sel_email, new_name, new_role, new_status)
        # load_users는 @st.cache_data라 캐시를 비워야 표·메트릭이 즉시 갱신된다.
        load_users.clear()
        st.toast(f"**{new_name}** 저장됨 · 대상자 재로그인 후 적용", icon="✅")
        st.rerun()

st.divider()

# ── Raw Data (읽기 전용) ──────────────────────────────────
st.subheader("Raw Data")

# 인원 통계 (4열 메트릭)
c_all, c_admin, c_editor, c_viewer = st.columns(4)
c_all.metric("전체 사용자", len(users_df))
c_admin.metric("관리자", int(counts.get("admin", 0)))
c_editor.metric("편집자", int(counts.get("editor", 0)))
c_viewer.metric("뷰어", int(counts.get("viewer", 0)))

# 비활성(Disable) 계정만 행 전체 회색으로 강조하고, role 라벨은 한글로 표시한다.
def _style(row):
    return ["color:#9aa0a6"] * len(row) if row["status"] == "Disable" else [""] * len(row)

styler = users_df.style.apply(_style, axis=1).format({"role": lambda r: ROLE_LABEL.get(r, r)})
st.dataframe(styler, width="stretch", hide_index=True)
