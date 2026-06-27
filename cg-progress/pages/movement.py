import streamlit as st

from constants import BOARD_CONFIG, BOARD_LABELS, MOVEMENT_LABEL, MOVEMENT_TYPES
from database import (add_movement_batch, delete_movement, load_movements,
                      outbound_serial)
from ui import confirm_dialog, flash, map_oids

role = st.session_state.get("role", "viewer")

if role != "admin":
    st.error("관리자만 접근할 수 있습니다.")
    st.stop()

st.title("입출고 관리")
st.caption("입고는 수량만큼 serial_number가 순차 채번되고, 출고는 입고된 Serial 중에서 선택합니다.")


class MovementBoard:
    """보드 한 종의 입출고 등록 + 조회(Raw Data) 화면.

    보드는 탭으로 고정되므로 등록 폼에 '보드 종류' 선택은 없다(탭의 보드로 고정).
    위젯·세션 key는 모두 prefix로 네임스페이스해 탭 간 충돌을 막는다(functional_test.py와 동일).
    """

    def __init__(self, label: str, cfg: dict) -> None:
        self.label = label
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]

    def _key(self, name: str) -> str:
        return f"{self.prefix}_{name}"

    # ── 등록 패널 ─────────────────────────────────────────────
    # 입고: 수량만큼 이 보드의 기존 최대 번호 다음부터 serial을 순차 채번한다(예: H0020까지 → 10 → H0021~H0030).
    # 출고: 새 번호를 채번하지 않고, 입고된(type=Inbound) Serial을 multiselect로 골라 출고 처리한다.
    def render_register(self) -> None:
        # 유형은 폼 '밖'에 둬 선택 즉시 rerun → 입고/출고에 맞는 입력 칸으로 전환한다.
        # (폼 안 위젯은 제출 전까지 rerun을 일으키지 않아 칸을 전환할 수 없다.)
        mtype = st.selectbox("유형", options=MOVEMENT_TYPES,
                             format_func=MOVEMENT_LABEL.get, key=self._key("mtype"))
        if mtype == "Inbound":
            self._render_inbound_form()
        else:
            self._render_outbound_form()

    def _render_inbound_form(self) -> None:
        with st.form(self._key("inbound_form"), clear_on_submit=True):
            # 1행: 생산 업체 / 2행: 일자·수량(가로로 나란히)
            manufacturer = st.text_input("생산 업체", key=self._key("mf")).strip()
            c1, c2 = st.columns(2)
            mdate = c1.date_input("일자", key=self._key("in_date"))
            qty = c2.number_input("수량", min_value=1, value=1, step=1, key=self._key("qty"))
            submitted = st.form_submit_button("등록", type="primary", width="stretch")

        if not submitted:
            return
        if not manufacturer:
            st.toast("제조사를 입력하세요.", icon="⚠️")
            return
        serials = add_movement_batch(
            self.prefix, self.digits, manufacturer, "Inbound", mdate.strftime("%Y-%m-%d"),
            int(qty), st.user.oid,
        )
        rng = serials[0] if len(serials) == 1 else f"{serials[0]}~{serials[-1]}"
        st.toast(f"입고 {rng} ({len(serials)}건) 등록됨", icon="✅")
        st.rerun()

    def _render_outbound_form(self) -> None:
        # 입고된(type=Inbound) Serial만 출고 후보로 보여준다.
        df = load_movements()
        inbounded = sorted(
            df[df["serial_number"].str.startswith(self.prefix) & (df["type"] == "Inbound")]
            ["serial_number"].tolist()
        )
        with st.form(self._key("outbound_form"), clear_on_submit=True):
            # 1행: Serial 번호(multiselect) / 2행: 일자
            serials = st.multiselect("Serial 번호", inbounded, key=self._key("out_serials"),
                                     placeholder="출고할 Serial 선택")
            mdate = st.date_input("일자", key=self._key("out_date"))
            submitted = st.form_submit_button("등록", type="primary", width="stretch")

        if not submitted:
            return
        if not serials:
            st.toast("출고할 Serial을 선택하세요.", icon="⚠️")
            return
        date = mdate.strftime("%Y-%m-%d")
        for s in serials:
            outbound_serial(s, date, st.user.oid)
        st.toast(f"출고 {len(serials)}건 등록됨", icon="✅")
        st.rerun()

    # ── Raw Data (읽기 전용) ──────────────────────────────────
    def render_records(self) -> None:
        st.subheader("Raw Data")

        # 이 보드(prefix)의 행만 추려 serial_number 오름차순으로 표시한다.
        df = load_movements()
        df = df[df["serial_number"].str.startswith(self.prefix)]
        if df.empty:
            st.info("입출고된 데이터가 없습니다.")
            return
        df = df.sort_values("serial_number", ascending=True)

        col1, col2 = st.columns(2)
        col1.metric("입고수량", int((df["type"] == "Inbound").sum()))
        col2.metric("출고수량", int((df["type"] == "Outbound").sum()))

        # ── 삭제 (관리자) ─────────────────────────────────────
        # 직전 실행에서 삭제됐다면 다이얼로그가 닫힌 뒤 토스트로 알린다.
        flash(self._key("del_msg"), icon="🗑️")

        def _delete(serial: str) -> None:
            delete_movement(serial)
            st.session_state[self._key("del_msg")] = f"**{serial}** 입출고 기록이 삭제되었습니다."

        # Serial 필터: 미선택이면 전체 표시, 선택 시 해당 Serial만 표시(단일 선택). 선택한 Serial이 삭제 대상이다.
        sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
        selected = sel_col.selectbox("Serial 번호 선택", df["serial_number"].tolist(), index=None,
                                     placeholder="전체 (선택 시 해당 Serial만 표시)",
                                     key=self._key("filter_serial"))
        if btn_col.button(":material/delete: 삭제", type="primary", width="stretch",
                          disabled=selected is None, key=self._key("del_btn")):
            confirm_dialog("입출고 삭제 확인", body=f"**{selected}** 의 입출고 기록을 삭제합니다.",
                           ok_label=":material/check: 확인", on_confirm=lambda: _delete(selected))

        # 선택 시 해당 Serial만 표시(미선택이면 전체). verify_by(oid)는 현재 이름으로 변환.
        view = df if selected is None else df[df["serial_number"] == selected]
        view = map_oids(view, "verify_by")
        st.dataframe(view, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    board = MovementBoard(label, BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        board.render_register()
        st.divider()
        board.render_records()
