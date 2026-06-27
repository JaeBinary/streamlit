"""기능 테스트·코팅 입력 위자드의 공통 골격.

두 위자드는 ① 기본 정보(Serial·날짜·담당자) 확인 → ② 스텝 입력 → 저장 확인 → 저장,
그리고 Raw Data 조회/삭제까지 흐름이 거의 같다. 다른 부분은 '스텝 입력 화면'(타이머 유무·
입력칸 수)과 저장 행/요약표뿐이다. 공통부는 여기 BaseWizard에 두고, 서브클래스는 차이만 구현한다.

서브클래스가 채울 것
  클래스 속성: item_col, tester_col, item_metric_label, exists_msg, delete_kind
  메서드     : _load_df, _delete_one, _build_summary, _build_rows, _insert,
               _init_step, _reset, _render_step_wizard, _download_button(기본 no-op)

세션 상태는 prefix로 네임스페이스해 탭 간 충돌을 막는다.
  {p}_base   : {"serial", "test_datetime", "tested_by"(oid), "tested_by_name"(표시용)}
  {p}_step   : 현재 스텝 인덱스   {p}_values : {스텝 인덱스: 측정값}
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from ui import confirm_dialog, flash, hide_df_toolbar, map_oids


def _role() -> str:
    # wizard.py는 1회만 import되므로 role을 모듈 전역에 두면 첫 값에 고정된다.
    # 권한은 매 rerun 갱신돼야 하니 호출 시점에 session_state에서 읽는다.
    return st.session_state.get("role", "viewer")


def can_edit() -> bool:
    return _role() in ("admin", "editor")


class BaseWizard:
    # 서브클래스가 덮어쓰는 표시·매핑 설정(기본값은 기능 테스트 기준).
    item_col = "test_item"          # render_records 메트릭·매핑 컬럼
    tester_col = "test_By"          # oid→이름 변환 대상 컬럼
    item_metric_label = "고유 Test Item 수"
    exists_msg = "이미 테스트를 완료하였습니다."
    delete_kind = "데이터"           # 삭제 다이얼로그 본문: "모든 {delete_kind}를 삭제합니다"

    def __init__(self, cfg: dict) -> None:
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]
        # Serial 입력 예시(placeholder·에러 문구 공용): 예) H0021
        self.example = f"{self.prefix}{21:0{self.digits}d}"

    # ── 세션 키 / 값 헬퍼 (prefix 네임스페이스) ───────────────
    def _key(self, name: str) -> str:
        return f"{self.prefix}_{name}"

    def _get(self, name: str, default=None):
        return st.session_state.get(self._key(name), default)

    def _set(self, name: str, value) -> None:
        st.session_state[self._key(name)] = value

    # ── Serial 정규화 ─────────────────────────────────────────
    def _normalize_serial(self, raw: str) -> str | None:
        """접두사 + 숫자 N자리로 정규화. '21'·'h21'·'0021' → 'H0021'. 형식 오류 시 None."""
        s = raw.strip().upper().removeprefix(self.prefix)
        if not s.isdigit() or len(s) > self.digits:
            return None
        return f"{self.prefix}{int(s):0{self.digits}d}"

    # ── 입력 진입점 ───────────────────────────────────────────
    def render_input(self) -> None:
        """① 기본 정보 확인 → ② 스텝 입력 → 저장 확인 → 저장."""
        flash(self._key("save_msg"), icon="💾")  # 직전 저장 결과를 모달이 닫힌 뒤 토스트로 알린다
        if self._get("base") is None:
            self._render_base_form()
        else:
            self._render_step_wizard()

    def _render_base_form(self) -> None:
        # Enter → '확인' 제출이 되도록 폼으로 묶는다(submit이 '확인' 하나뿐이라 Enter는 확인으로 간다).
        with st.form(self._key("base_form"), border=True, clear_on_submit=False):
            col1, col2, col3 = st.columns(3)
            serial = col1.text_input("Serial 번호", placeholder=f"예시: 21 or {self.example}",
                                     key=self._key("in_serial"))
            # 날짜는 오늘로, 진행자는 로그인 사용자 이름으로 자동 고정한다(비활성·표시용).
            # 저장은 이름이 아니라 불변 oid로 하므로 AD에서 이름이 바뀌어도 과거 기록과의 매핑이 끊기지 않는다.
            test_date = col2.date_input("날짜", key=self._key("in_date"), disabled=True)
            col3.text_input("진행자", value=st.user.name, key=self._key("in_by"), disabled=True)
            confirmed = st.form_submit_button("확인", type="primary", width="stretch",
                                              key=self._key("confirm"))

        if not confirmed:
            return

        serial_norm = self._normalize_serial(serial)
        if serial_norm is None:
            st.error(f"Serial 번호는 '{self.prefix} + 숫자 {self.digits}자리' 형식입니다. "
                     f"숫자만 입력해도 됩니다 (예: 21 → {self.example}).")
            return
        if not st.user.oid:
            st.error("로그인 정보를 확인할 수 없습니다. 다시 로그인해 주세요.")
            return

        # 이미 입력된 Serial이면 진입을 막는다(중복 저장 방지). 검수 중·승인 모두 포함해 막는다.
        if serial_norm in set(self._load_df()["serial_number"]):
            st.toast(self.exists_msg, icon="⚠️")
            return

        self._set("base", {
            "serial": serial_norm,
            # 값은 시각까지 저장, 표시는 호출부에서 date만 잘라 쓴다.
            "test_datetime": datetime.combine(test_date, datetime.now().time())
                                     .strftime("%Y-%m-%d %H:%M:%S"),
            "tested_by": st.user.oid,        # DB 저장용 — 불변 oid
            "tested_by_name": st.user.name,  # 화면 표시용 — 현재 로그인 이름
        })
        self._set("step", 0)
        self._set("values", {})
        self._init_step()  # 스텝0 입력칸을 빈값으로 초기화(서브클래스마다 칸 구성이 다름)
        st.rerun()

    # ── 취소 헤더(캡션 좌 + 취소 버튼 우상단) ─────────────────
    def _render_cancel_header(self, base: dict) -> None:
        # 아이콘만 남긴 tertiary 버튼을 키 있는 컨테이너에 담고 align-items:flex-end로 우측 끝에 붙인다.
        info_col, cancel_col = st.columns([9, 1], vertical_alignment="center")
        info_col.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
        cancel_key = self._key("cancel_box")
        with cancel_col.container(key=cancel_key):
            st.button(":material/close:", type="tertiary", help="취소",
                      on_click=self._reset, key=self._key("cancel"))
        st.html(f"<style>.st-key-{cancel_key}{{align-items:flex-end}}</style>")

    # ── 저장 확인 다이얼로그 ──────────────────────────────────
    def _confirm_save_dialog(self) -> None:
        """입력값을 모아 보여주고 최종 저장/취소를 받는 모달. confirm_save 플래그가 있을 때 연다."""
        base = self._get("base")
        values = self._get("values")

        @st.dialog("데이터 확인")
        def _dlg() -> None:
            st.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
            st.markdown("아래 측정값을 저장합니다.")
            st.dataframe(pd.DataFrame(self._build_summary(values)), width="stretch", hide_index=True)
            hide_df_toolbar("dialog")  # 확인용 읽기 전용 표라 툴바 숨김

            cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 확인 우측
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("save_ok")):
                self._insert(self._build_rows(base, values))
                # 저장 시점엔 '검수 중'이며, 관리자가 검수 리스트에서 승인해야 최종 저장된다.
                self._set("save_msg", f"**{base['serial']}** 저장됨 · 관리자 검수 대기 중")
                self._reset()
                st.rerun()
            if cancel_col.button(":material/close: 취소", width="stretch",
                                 key=self._key("save_cancel")):
                st.rerun()  # 모달만 닫고 마지막 스텝에 머문다(confirm_save는 열 때 이미 소비됨)

        _dlg()

    # ── 데이터 조회 (Raw Data) ────────────────────────────────
    def render_records(self) -> None:
        df = self._load_df()
        st.subheader("Raw Data")

        # 보드 접두사로 시작하고 검수 완료(verify_by NOT NULL)된 행만 표시한다.
        df = df[df["serial_number"].str.startswith(self.prefix) & df["verify_by"].notna()]
        if df.empty:
            st.info("검수 완료된 데이터가 없습니다.")
            return

        col1, col2 = st.columns(2)
        col1.metric("고유 Serial 수", df["serial_number"].nunique())
        col2.metric(self.item_metric_label, df[self.item_col].nunique())

        options = df["serial_number"].unique().tolist()
        flash(self._key("del_msg"), icon="🗑️")  # 직전 삭제 결과를 모달이 닫힌 뒤 토스트로 알린다

        def _delete(serials: list[str]) -> None:
            for s in serials:
                self._delete_one(s)
            joined = ", ".join(f"**{s}**" for s in serials)
            st.session_state[self._key("del_msg")] = f"{joined} 의 데이터가 삭제되었습니다."

        placeholder = "전체 (선택 시 해당 Serial만 표시)"
        if _role() == "admin":
            # 관리자만 선택 Serial을 삭제할 수 있다(우측 삭제 버튼).
            sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
            selected = sel_col.multiselect("Serial 번호 선택", options,
                                           placeholder=placeholder, key=self._key("filter_serial"))
            if btn_col.button(":material/delete: 삭제", type="primary", width="stretch",
                              disabled=not selected, key=self._key("del_btn")):
                joined = ", ".join(f"**{s}**" for s in selected)
                confirm_dialog("데이터 삭제 확인",
                               body=f"{joined} 의 모든 {self.delete_kind}를 삭제합니다.",
                               ok_label=":material/check: 확인",
                               on_confirm=lambda: _delete(selected))
        else:
            selected = st.multiselect("Serial 번호 선택", options,
                                      placeholder=placeholder, key=self._key("filter_serial"))

        # 선택 Serial로 필터링(미선택이면 전체). tester·verify_by의 불변 oid는 현재 이름으로 변환.
        view = df if not selected else df[df["serial_number"].isin(selected)]
        view = map_oids(view, self.tester_col, "verify_by")
        self._download_button(view)  # 양식 매핑이 있는 보드만 버튼 노출(없으면 no-op)
        st.dataframe(view, width="stretch", hide_index=True)

    # ── 서브클래스 훅 ─────────────────────────────────────────
    def _load_df(self):
        raise NotImplementedError

    def _delete_one(self, serial: str) -> None:
        raise NotImplementedError

    def _build_summary(self, values: dict) -> list[dict]:
        raise NotImplementedError

    def _build_rows(self, base: dict, values: dict) -> list:
        raise NotImplementedError

    def _insert(self, rows: list) -> None:
        raise NotImplementedError

    def _init_step(self) -> None:
        raise NotImplementedError

    def _reset(self) -> None:
        raise NotImplementedError

    def _render_step_wizard(self) -> None:
        raise NotImplementedError

    def _download_button(self, view) -> None:
        pass  # 양식이 없는 보드는 버튼을 노출하지 않는다
