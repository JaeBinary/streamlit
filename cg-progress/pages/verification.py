import pandas as pd
import streamlit as st

from constants import board_by_prefix, summary_records
from database import delete_serial, load_records, verify_serial

# 관리자 전용 페이지. streamlit_app.py에서 admin일 때만 네비게이션에 노출하지만,
# 페이지 단에서도 한 번 더 막아 URL 직접 접근 등 우회 진입을 차단한다(다층 방어).
role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("Verification")
st.caption('저장된 "데이터를 검수"하여 승인하거나 반려(삭제)합니다.')

# 직전 실행(승인·반려)의 결과를 rerun 후 토스트로 알린다.
msg = st.session_state.pop("verify_msg", None)
if msg:
    st.toast(msg, icon="✅")

# verify_by가 NULL인 행이 '검수 중'이다(전체 공개 조회 후 파이썬에서 필터).
pending = load_records()
pending = pending[pending["verify_by"].isna()]

if pending.empty:
    st.info("검수 대기 중인 데이터가 없습니다.")
    st.stop()

st.markdown(f"#### 검수 대기 {pending['serial'].nunique()}건")

# Serial 단위로 한 번에 승인/반려하므로 다이얼로그도 Serial 기준. (한 번에 하나만 열림)
@st.dialog("데이터 삭제")
def _confirm_reject(serial: str) -> None:
    st.markdown(f"**{serial}** 의 모든 데이터를 삭제합니다. 되돌릴 수 없습니다.")
    cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 삭제 우측
    if ok_col.button(":material/delete: 삭제", type="primary", width="stretch", key="reject_ok"):
        delete_serial(serial)
        st.session_state["verify_msg"] = f"**{serial}** 반려(삭제)되었습니다."
        st.rerun()
    if cancel_col.button(":material/close: 취소", width="stretch", key="reject_cancel"):
        st.rerun()

# 검수 카드 안의 표는 읽기 전용이라 dataframe 툴바를 숨긴다(한 번만 주입).
st.html('<style>[data-testid="stDataFrame"] [data-testid="stElementToolbar"]{display:none}</style>')

# Serial별로 묶어 카드로 표시. load_records가 test_item 숫자순으로 정렬해 항목 순서가 보장된다.
for serial, group in pending.groupby("serial", sort=False):
    board = board_by_prefix(serial)
    steps = board["steps"] if board else []
    head = group.iloc[0]

    with st.container(border=True):
        st.markdown(f"#### {serial}")
        st.caption(f"{head['test_datetime'][:10]}  ·  {head['tested_by']}  ·  {len(group)}개 항목")

        # 데이터 확인 모달과 동일한 표(공용 summary_records). DB의 test_item(1-base)을
        # 스텝 인덱스(0-base)로 맞춰 측정값 dict를 만든 뒤 그대로 전달한다.
        values = {int(r["test_item"]) - 1: r["measurements"] for _, r in group.iterrows()}
        st.dataframe(pd.DataFrame(summary_records(steps, values)),
                     width="stretch", hide_index=True)

        reject_col, approve_col = st.columns(2)
        if reject_col.button(":material/close: 반려", width="stretch", key=f"reject_{serial}"):
            _confirm_reject(serial)
        if approve_col.button(":material/check: 승인", type="primary", width="stretch",
                              key=f"approve_{serial}"):
            verify_serial(serial, st.user.email)
            st.session_state["verify_msg"] = f"**{serial}** 승인되었습니다."
            st.rerun()
