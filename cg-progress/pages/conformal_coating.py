from datetime import datetime

import streamlit as st

from constants import (BOARD_CONFIG, BOARD_LABELS, COATING_MIN, COATING_POINT_ITEM,
                       COATING_POINTS, COATING_UNIT, coating_summary_records)
from database import (delete_coating_serial, insert_coating_records,
                      load_coating_records)
from export import build_filled_form
from wizard import BaseWizard, can_edit

st.title("Conformal Coating")
st.caption('CG PCBA 5종에 대한 "컨포멀 코팅" 두께를 측정합니다.')


class CoatingWizard(BaseWizard):
    """보드 한 종의 코팅 두께 위자드. 입력만 두 단계로 나뉜다(step 0=TOP-1~4, step 1=BOTTOM-1~4, 각 4열 동시 입력).
    측정 포인트(8개)는 모든 보드 공통(COATING_POINTS). 공통 골격은 BaseWizard에 있고 여기선 단계 입력만 구현한다.
      {p}_c{idx} : 각 입력칸 값(위젯 key). 단계 이동 콜백에서 values와 주고받는다."""

    # 코팅 테이블은 컬럼·라벨이 기능 테스트와 달라 BaseWizard 기본값을 덮어쓴다.
    item_col = "coating_point"
    tester_col = "test_by"
    item_metric_label = "고유 Point 수"
    exists_msg = "이미 코팅 측정을 완료하였습니다."
    delete_kind = "코팅 데이터"

    NSTEPS = 2
    ROW_LABELS = ["TOP", "BOTTOM"]

    def __init__(self, cfg: dict) -> None:
        super().__init__(cfg)
        self.points = COATING_POINTS
        self.coating_form = cfg.get("coating_form")  # Raw Data 공식 양식 다운로드용(없으면 버튼 비노출)

    # ── 단계 ↔ 포인트 인덱스 매핑 ─────────────────────────────
    def _step_indices(self, step: int) -> range:
        """단계의 포인트 인덱스 4개. step 0 → 0~3(TOP), step 1 → 4~7(BOTTOM)."""
        return range(step * 4, step * 4 + 4)

    def _cell_key(self, gidx: int) -> str:
        return self._key(f"c{gidx}")

    def _commit_step(self, step: int) -> None:
        """현재 단계 입력칸 4개 값을 values(단일 출처)로 옮긴다(폼 제출 시 위젯 값이 먼저 커밋된 뒤 돈다)."""
        values = self._get("values")
        for gidx in self._step_indices(step):
            values[gidx] = st.session_state.get(self._cell_key(gidx), "")

    def _seed_step(self, step: int) -> None:
        """다음에 그릴 단계의 입력칸을 values 저장값으로 채운다(뒤로 가기 시 값 복원·없으면 빈값)."""
        values = self._get("values")
        for gidx in self._step_indices(step):
            st.session_state[self._cell_key(gidx)] = values.get(gidx, "")

    # ── BaseWizard 훅 ─────────────────────────────────────────
    def _load_df(self):
        return load_coating_records()

    def _delete_one(self, serial: str) -> None:
        delete_coating_serial(serial)

    def _build_summary(self, values: dict) -> list[dict]:
        return coating_summary_records(values)

    def _build_rows(self, base: dict, values: dict) -> list:
        return [(base["serial"], self.points[i], base["test_datetime"], base["tested_by"],
                 values.get(i, "")) for i in range(len(self.points))]

    def _insert(self, rows: list) -> None:
        insert_coating_records(rows)

    def _init_step(self) -> None:
        self._seed_step(0)  # 첫 단계 입력칸 4개를 빈값으로 초기화(이전 잔류값 차단)

    def _reset(self) -> None:
        for name in ("base", "step", "values", "confirm_save"):
            st.session_state.pop(self._key(name), None)
        # Serial 입력칸은 비워 다음 측정을 새 번호로 시작한다(날짜·담당자는 유지).
        st.session_state.pop(self._key("in_serial"), None)
        # 입력칸 8개도 모두 비운다(다음 Serial에 이전 값이 새지 않도록).
        for gidx in range(len(self.points)):
            st.session_state.pop(self._cell_key(gidx), None)

    def _download_button(self, view) -> None:
        if not self.coating_form:
            return
        # 코팅 view를 build_filled_form이 기대하는 스키마로 변환한다:
        #   coating_point("T1"~"B4") → test_item(1~8 행순번), test_by → test_By(이미 이름).
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

    # ── 단계 입력 화면 ────────────────────────────────────────
    def _render_step_wizard(self) -> None:
        base = self._get("base")
        step = self._get("step")
        is_last = step == self.NSTEPS - 1
        row_label = self.ROW_LABELS[step]

        # 저장 확인 요청이 있으면 모달을 연다(본문에서 호출해야 열림). 플래그 '즉시 소비'로 한 번만 연다
        # (st.tabs는 매 rerun에 모든 탭 코드를 실행하므로).
        if self._get("confirm_save"):
            self._set("confirm_save", False)
            self._confirm_save_dialog()

        with st.container(border=True):
            self._render_cancel_header(base)
            st.progress(step / self.NSTEPS, text=f"{step}/{self.NSTEPS} 완료")
            st.markdown(f"#### {row_label} 면 두께 측정")
            st.caption(f"기준: ≥ {COATING_MIN} {COATING_UNIT} (상한 없음)")

            next_label = ":material/save: 저장" if is_last else "다음 :material/arrow_forward:"
            # 조회 전용(viewer)은 단계는 둘러보되 마지막 '저장'만 막는다.
            save_blocked = is_last and not can_edit()
            help_txt = "조회 전용 계정은 저장할 수 없습니다." if save_blocked else None

            # 폼 key에 step을 포함해 단계 이동마다 remount → 미제출 입력 버퍼가 폐기된다.
            with st.form(self._key(f"step_form_{step}"), border=False, clear_on_submit=False):
                cols = st.columns(4)
                for col, gidx in zip(cols, self._step_indices(step)):
                    col.text_input(f"{self.points[gidx]} ({COATING_UNIT})", key=self._cell_key(gidx))
                # '다음/저장'을 '이전'보다 먼저 정의해 Enter가 항상 다음으로 가게 한다(Enter=첫 submit).
                # 배치는 다음=우측·이전=좌측이 되도록 컬럼 객체에 역순으로 그린다(정의순≠배치순).
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


# ── 탭 구성 ───────────────────────────────────────────────
# 코팅 포인트는 모든 보드 공통이라 5종 모두 동일하게 입력 위자드를 노출한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = CoatingWizard(BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        wizard.render_input()
        st.divider()
        wizard.render_records()
