from datetime import datetime

import streamlit as st

from constants import (BOARD_CONFIG, BOARD_LABELS, COATING_MIN, COATING_POINTS,
                       COATING_UNIT, coating_summary_records)
from database import (delete_coating_serial, insert_coating_records,
                      load_coating_records, user_names)
from export import build_filled_form
import pandas as pd

# 코팅 포인트(T1~B4) → 양식 측정값 행 순번(1~8). 양식 6행부터 COATING_POINTS 순서로 들어간다.
COATING_POINT_ITEM = {p: i + 1 for i, p in enumerate(COATING_POINTS)}

role = st.session_state.get("role", "viewer")
can_edit = role in ("admin", "editor")

st.title("Conformal Coating")
st.caption('CG PCBA 5종에 대한 "컨포멀 코팅" 두께를 측정합니다.')


class CoatingWizard:
    """보드 한 종의 코팅 두께 입력 위자드 + 조회 화면.

    구조는 기능 테스트(2_functional_test.py)와 동일하나, 측정 입력만 두 단계로 나뉜다.
      step 0 : TOP-1~4를 4열로 동시 입력
      step 1 : BOTTOM-1~4를 4열로 동시 입력 → 저장 확인
    측정 포인트(8개)는 모든 보드 공통(COATING_POINTS). 진행 상태는 prefix로 네임스페이스한
    세션 키에 보관해 탭 간 충돌을 막는다.
      {p}_base   : {"serial", "test_datetime", "tested_by"(oid), "tested_by_name"(표시용)}
      {p}_step   : 현재 단계(0=TOP, 1=BOTTOM)
      {p}_values : {포인트 인덱스(0~7): 측정값}
      {p}_c{idx} : 각 입력칸 값(위젯 key). 단계 이동 콜백에서 values와 주고받는다.
    """

    # 두 단계 × 4포인트. 단계별 라벨은 화면 머리글에 쓴다.
    NSTEPS = 2
    ROW_LABELS = ["TOP", "BOTTOM"]

    def __init__(self, cfg: dict) -> None:
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]
        self.points = COATING_POINTS
        # Raw Data 공식 양식(코팅) 다운로드용 매핑(없으면 버튼 비노출)
        self.coating_form = cfg.get("coating_form")
        # Serial 입력 예시 (placeholder·에러 문구 공용): 예) H0021
        self.example = f"{self.prefix}{21:0{self.digits}d}"

    # ── 세션 키 / 값 헬퍼 (prefix 네임스페이스) ───────────────
    def _key(self, name: str) -> str:
        return f"{self.prefix}_{name}"

    def _get(self, name: str, default=None):
        return st.session_state.get(self._key(name), default)

    def _set(self, name: str, value) -> None:
        st.session_state[self._key(name)] = value

    # ── 단계 ↔ 포인트 인덱스 매핑 ─────────────────────────────
    def _step_indices(self, step: int) -> range:
        """단계의 포인트 인덱스 4개. step 0 → 0~3(TOP), step 1 → 4~7(BOTTOM)."""
        return range(step * 4, step * 4 + 4)

    def _cell_key(self, gidx: int) -> str:
        return self._key(f"c{gidx}")

    def _commit_step(self, step: int) -> None:
        """현재 단계의 입력칸 4개 값을 values(단일 출처)로 옮긴다.
        폼 제출 시 위젯 값이 session_state에 먼저 커밋된 뒤 이 콜백이 돌므로 값이 보장된다."""
        values = self._get("values")
        for gidx in self._step_indices(step):
            values[gidx] = st.session_state.get(self._cell_key(gidx), "")

    def _seed_step(self, step: int) -> None:
        """다음에 그릴 단계의 입력칸을 values의 저장값으로 채운다(뒤로 가기 시 값 복원·없으면 빈값).
        values를 단일 출처로 삼아, 안 그려진 단계의 위젯 상태가 사라져도 영향받지 않는다."""
        values = self._get("values")
        for gidx in self._step_indices(step):
            st.session_state[self._cell_key(gidx)] = values.get(gidx, "")

    # ── Serial 정규화 ─────────────────────────────────────────
    def _normalize_serial(self, raw: str) -> str | None:
        """접두사 + 숫자 N자리로 정규화. '21'·'h21'·'0021' → 'H0021'. 형식 오류 시 None."""
        s = raw.strip().upper().removeprefix(self.prefix)
        if not s.isdigit() or len(s) > self.digits:
            return None
        return f"{self.prefix}{int(s):0{self.digits}d}"

    # ── 위자드 콜백 (재실행 '전' 실행 → rerun 1회로 깜빡임 없음) ──
    def _advance_step(self) -> None:
        """현재 단계 값을 저장하고 다음 단계로(마지막이면 저장 확인 다이얼로그 요청)."""
        step = self._get("step")
        self._commit_step(step)
        if step >= self.NSTEPS - 1:
            self._set("confirm_save", True)
        else:
            self._set("step", step + 1)
            self._seed_step(step + 1)

    def _prev_step(self) -> None:
        step = self._get("step")
        if step > 0:
            self._commit_step(step)
            self._set("step", step - 1)
            self._seed_step(step - 1)

    def _reset(self) -> None:
        for name in ("base", "step", "values", "confirm_save"):
            st.session_state.pop(self._key(name), None)
        # Serial 입력칸은 비워 다음 측정을 새 번호로 시작한다(날짜·담당자는 유지).
        st.session_state.pop(self._key("in_serial"), None)
        # 입력칸 8개도 모두 비운다(다음 Serial에 이전 값이 새지 않도록).
        for gidx in range(len(self.points)):
            st.session_state.pop(self._cell_key(gidx), None)

    # ── 저장 확인 다이얼로그 ──────────────────────────────────
    def _confirm_save_dialog(self) -> None:
        """입력값을 모아 보여주고 최종 저장/취소를 받는 모달. confirm_save 플래그가 있을 때 연다."""
        base = self._get("base")
        values = self._get("values")

        @st.dialog("데이터 확인")
        def _dlg() -> None:
            st.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
            st.markdown("아래 측정값을 저장합니다.")
            st.dataframe(pd.DataFrame(coating_summary_records(values)),
                         width="stretch", hide_index=True)
            # 확인용 읽기 전용 표라 dataframe 툴바를 숨긴다(2_functional_test.py와 동일).
            st.html('<style>[role="dialog"] [data-testid="stElementToolbar"]{display:none}</style>')

            cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 확인 우측
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("save_ok")):
                rows = [
                    (base["serial"], self.points[i], base["test_datetime"], base["tested_by"],
                     values.get(i, ""))
                    for i in range(len(self.points))
                ]
                insert_coating_records(rows)
                self._set("save_msg", f"**{base['serial']}** 저장됨 · 관리자 검수 대기 중")
                self._reset()
                st.rerun()
            if cancel_col.button(":material/close: 취소", width="stretch",
                                 key=self._key("save_cancel")):
                # 모달만 닫고 마지막 단계에 그대로 머문다(confirm_save는 열 때 이미 소비됨).
                st.rerun()

        _dlg()

    # ── 입력 폼 ───────────────────────────────────────────────
    def render_input(self) -> None:
        """① 기본 정보(Serial·날짜·담당자) 확인 → ② TOP/BOTTOM 측정값 입력 → 저장 확인 → 저장."""
        msg = st.session_state.pop(self._key("save_msg"), None)
        if msg:
            st.toast(msg, icon="💾")

        if self._get("base") is None:
            self._render_base_form()
        else:
            self._render_step_wizard()

    def _render_base_form(self) -> None:
        with st.form(self._key("base_form"), border=True, clear_on_submit=False):
            col1, col2, col3 = st.columns(3)
            serial = col1.text_input("Serial 번호", placeholder=f"예시: 21 or {self.example}",
                                     key=self._key("in_serial"))
            # 날짜는 오늘로, 진행자는 로그인 사용자 이름으로 자동 고정한다(비활성·표시용).
            # 저장은 이름이 아니라 불변 oid로 한다(조회 화면에선 oid→현재 이름으로 변환).
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

        # 이미 코팅이 입력된 Serial이면 진입을 막는다(중복 저장 방지). 검수 중·승인 모두 포함.
        existing = load_coating_records()["serial_number"]
        if serial_norm in set(existing):
            st.toast("이미 코팅 측정을 완료하였습니다.", icon="⚠️")
            return

        self._set("base", {
            "serial": serial_norm,
            "test_datetime": datetime.combine(test_date, datetime.now().time())
                                     .strftime("%Y-%m-%d %H:%M:%S"),
            "tested_by": st.user.oid,        # DB 저장용 — 불변 oid
            "tested_by_name": st.user.name,  # 화면 표시용 — 현재 로그인 이름
        })
        self._set("step", 0)
        self._set("values", {})
        self._seed_step(0)  # 입력칸 4개를 빈값으로 초기화(이전 잔류값 차단)
        st.rerun()

    def _render_step_wizard(self) -> None:
        base = self._get("base")
        step = self._get("step")
        is_last = step == self.NSTEPS - 1
        row_label = self.ROW_LABELS[step]

        # 저장 확인 요청이 있으면 모달을 연다(콜백이 아닌 본문에서 호출해야 모달이 열림).
        # 플래그를 '즉시 소비'해 한 번만 연다(st.tabs는 모든 탭 코드가 매 rerun 실행되므로).
        if self._get("confirm_save"):
            self._set("confirm_save", False)
            self._confirm_save_dialog()

        with st.container(border=True):
            # 캡션(좌) + 취소 버튼(우상단). 취소는 상태만 되돌리므로 폼 밖 일반 버튼.
            info_col, cancel_col = st.columns([9, 1], vertical_alignment="center")
            info_col.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
            cancel_key = self._key("cancel_box")
            with cancel_col.container(key=cancel_key):
                st.button(":material/close:", type="tertiary", help="취소",
                          on_click=self._reset, key=self._key("cancel"))
            st.html(f"<style>.st-key-{cancel_key}{{align-items:flex-end}}</style>")
            st.progress(step / self.NSTEPS, text=f"{step}/{self.NSTEPS} 완료")
            st.markdown(f"#### {row_label} 면 두께 측정")
            st.caption(f"기준: ≥ {COATING_MIN} {COATING_UNIT} (상한 없음)")

            next_label = ":material/save: 저장" if is_last else "다음 :material/arrow_forward:"
            # 조회 전용(viewer)은 단계는 둘러보되 마지막 '저장'만 막는다.
            save_blocked = is_last and not can_edit
            help_txt = "조회 전용 계정은 저장할 수 없습니다." if save_blocked else None

            # 폼 key에 step을 포함해 단계 이동마다 remount → 제출 안 된 입력 버퍼가 폐기된다.
            with st.form(self._key(f"step_form_{step}"), border=False, clear_on_submit=False):
                cols = st.columns(4)
                for col, gidx in zip(cols, self._step_indices(step)):
                    col.text_input(f"{self.points[gidx]} ({COATING_UNIT})", key=self._cell_key(gidx))
                # '다음/저장'을 '이전'보다 먼저 정의해 Enter가 항상 다음으로 가게 한다(Enter=첫 submit).
                # 단, 배치는 다음=우측·이전=좌측이 되도록 컬럼 객체에 역순으로 그린다(정의순≠배치순).
                if step > 0:
                    prev_col, next_col = st.columns(2)
                    next_col.form_submit_button(next_label, type="primary", width="stretch",
                                                key=self._key("submit_next"), on_click=self._advance_step,
                                                disabled=save_blocked, help=help_txt)
                    prev_col.form_submit_button(":material/arrow_back: 이전", width="stretch",
                                                key=self._key("submit_prev"), on_click=self._prev_step)
                else:
                    st.form_submit_button(next_label, type="primary", width="stretch",
                                          key=self._key("submit_next"), on_click=self._advance_step,
                                          disabled=save_blocked, help=help_txt)

    # ── 데이터 조회 (Raw Data) ────────────────────────────────
    def render_records(self) -> None:
        df = load_coating_records()
        st.subheader("Raw Data")

        # 보드 접두사로 시작하고 검수 완료(verify_by NOT NULL)된 행만 표시한다.
        df = df[df["serial_number"].str.startswith(self.prefix) & df["verify_by"].notna()]

        if df.empty:
            st.info("검수 완료된 데이터가 없습니다.")
            return

        col1, col2 = st.columns(2)
        col1.metric("고유 Serial 수", df["serial_number"].nunique())
        col2.metric("고유 Point 수", df["coating_point"].nunique())

        # Serial 필터: 미선택이면 전체 표시, 선택한 Serial들만 표시(다중 선택).
        options = df["serial_number"].unique().tolist()

        # 삭제 확인 다이얼로그. 내부 st.rerun()이 다이얼로그를 닫고 페이지를 재실행한다.
        @st.dialog("데이터 삭제 확인")
        def _confirm_delete(serials: list[str]) -> None:
            joined = ", ".join(f"**{s}**" for s in serials)
            st.markdown(f"{joined} 의 모든 코팅 데이터를 삭제합니다.")
            cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 확인/삭제 우측
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("del_ok")):
                for s in serials:
                    delete_coating_serial(s)
                self._set("del_msg", f"{joined} 의 데이터가 삭제되었습니다.")
                st.rerun()
            if cancel_col.button(":material/close: 취소", width="stretch", key=self._key("del_cancel")):
                st.rerun()

        # 직전 실행에서 삭제됐다면 다이얼로그가 닫힌 뒤 토스트로 알린다.
        msg = st.session_state.pop(self._key("del_msg"), None)
        if msg:
            st.toast(msg, icon="🗑️")

        PLACEHOLDER = "전체 (선택 시 해당 Serial만 표시)"
        if role == "admin":
            # 관리자만 선택 Serial을 삭제할 수 있다(우측 삭제 버튼).
            sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
            selected = sel_col.multiselect("Serial 번호 선택", options,
                                           placeholder=PLACEHOLDER, key=self._key("filter_serial"))
            if btn_col.button(":material/delete: 삭제", type="primary", width="stretch",
                              disabled=not selected, key=self._key("del_btn")):
                _confirm_delete(selected)
        else:
            selected = st.multiselect("Serial 번호 선택", options,
                                      placeholder=PLACEHOLDER, key=self._key("filter_serial"))

        # 선택 Serial로 필터링(미선택이면 전체). test_by·verify_by의 불변 oid는 현재 이름으로 변환.
        view = df if not selected else df[df["serial_number"].isin(selected)]
        names = user_names()
        view = view.assign(
            test_by=view["test_by"].map(names).fillna(view["test_by"]),
            verify_by=view["verify_by"].map(names).fillna(view["verify_by"]),
        )

        # 선택(미선택 시 전체) Serial을 공식 양식(.xlsx)에 채워 다운로드.
        # 코팅 view를 build_filled_form이 기대하는 스키마로 변환한다:
        #   coating_point("T1"~"B4") → test_item(1~8 행순번), test_by → test_By(이미 이름).
        if self.coating_form:
            form_view = view.assign(
                test_item=view["coating_point"].map(COATING_POINT_ITEM),
                test_By=view["test_by"],
            )
            st.download_button(
                ":material/download: Download XLSX",
                data=build_filled_form(self.coating_form["file"], self.coating_form["sheet"],
                                       self.coating_form["serial_col"], self.prefix,
                                       len(self.points), form_view),
                file_name=f"{self.coating_form['file'].removesuffix('.xlsx')}_{datetime.now():%y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=view.empty, width="stretch", key=self._key("dl_form"),
            )

        st.dataframe(view, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
# 코팅 포인트는 모든 보드 공통이라 5종 모두 동일하게 입력 위자드를 노출한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = CoatingWizard(BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        wizard.render_input()
        st.divider()
        wizard.render_records()
