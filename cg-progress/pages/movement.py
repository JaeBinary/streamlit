import streamlit as st

from constants import BOARD_CONFIG, BOARD_LABELS, MOVEMENT_LABEL, MOVEMENT_TYPES
from database import add_movement_batch, delete_movement, load_movements

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("입출고 관리")
st.caption("보드와 수량을 입력하면 serial_number가 순차 채번되어 등록됩니다.")

movements_df = load_movements()

# ── 등록 패널 ─────────────────────────────────────────────
# 보드를 고르고 수량을 입력하면, 그 보드의 기존 최대 번호 다음부터 수량만큼 serial을 채번한다.
# 예: H 보드에 H0020까지 있으면 10 입력 → H0021~H0030. type은 DB에 영문 저장, 화면엔 한글 라벨.
with st.form("add_movement", clear_on_submit=True):
    c1, c2 = st.columns(2)
    board = c1.selectbox("보드 종류", options=BOARD_LABELS)
    manufacturer = c2.text_input("생산 업체").strip()
    c3, c4, c5 = st.columns(3)
    mtype = c3.selectbox("유형", options=MOVEMENT_TYPES, format_func=MOVEMENT_LABEL.get)
    mdate = c4.date_input("일자")
    qty = c5.number_input("수량", min_value=1, value=1, step=1)
    submitted = st.form_submit_button("등록", type="primary", width="stretch")

if submitted:
    if not manufacturer:
        st.toast("제조사를 입력하세요.", icon="⚠️")
    else:
        cfg = BOARD_CONFIG[board]
        serials = add_movement_batch(
            cfg["prefix"], cfg["digits"], manufacturer, mtype, mdate.strftime("%Y-%m-%d"), int(qty)
        )
        rng = serials[0] if len(serials) == 1 else f"{serials[0]}~{serials[-1]}"
        st.toast(f"{MOVEMENT_LABEL[mtype]} {rng} ({len(serials)}건) 등록됨", icon="✅")
        st.rerun()

st.divider()

# ── Raw Data (읽기 전용) ──────────────────────────────────
st.subheader("Raw Data")

if not len(movements_df):
    st.info("입출고된 데이터가 없습니다.")
    st.stop()

# 보드별 입고 수량(type=Inbound) — 보드 prefix로 serial을 집계해 보드마다 한 칸씩 표시한다.
inbound = movements_df[movements_df["type"] == "Inbound"]
for col, label in zip(st.columns(len(BOARD_LABELS)), BOARD_LABELS):
    prefix = BOARD_CONFIG[label]["prefix"]
    qty = int(inbound["serial_number"].str.startswith(prefix).sum()) if len(inbound) else 0
    col.metric(label, qty)

# Raw Data는 원본 컬럼명(serial_number, manufacturer, type, date) 그대로 표시한다.
st.dataframe(movements_df, width="stretch", hide_index=True)

# ── 삭제 (관리자) ─────────────────────────────────────────
# 실수 삭제를 막으려 확인 다이얼로그를 띄운다. 확인 시 st.rerun()으로 다이얼로그를 닫고 화면을 갱신한다.
@st.dialog("입출고 삭제 확인")
def _confirm_delete(serial: str) -> None:
    st.markdown(f"**{serial}** 의 입출고 기록을 삭제합니다.")
    cancel_col, ok_col = st.columns(2)
    if ok_col.button(":material/check: 확인", type="primary", width="stretch", key="mv_del_ok"):
        delete_movement(serial)
        st.toast(f"**{serial}** 입출고 기록이 삭제되었습니다.", icon="🗑️")
        st.rerun()
    if cancel_col.button(":material/close: 취소", width="stretch", key="mv_del_cancel"):
        st.rerun()

if len(movements_df):
    sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    del_serial = sel_col.selectbox("삭제할 Serial", options=movements_df["serial_number"].tolist())
    if btn_col.button("삭제", width="stretch", icon=":material/delete:"):
        _confirm_delete(del_serial)
