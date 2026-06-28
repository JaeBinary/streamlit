import math
import time
from datetime import datetime

import streamlit as st

from lib.constants import BOARD_CONFIG, BOARD_LABELS, summary_records
from lib.database import delete_serial, insert_records, load_records
from lib.export import build_filled_form
from lib.ui import confirm_dialog
from lib.wizard import BaseWizard, can_edit

st.title("Functional Test")
st.caption('CG PCBA 5종에 대한 "기능 테스트"를 진행합니다.')


class BoardWizard(BaseWizard):
    """보드 한 종의 기능 테스트 위자드. 스텝마다 측정값 한 칸을 입력하며, 일부 스텝엔 안내용 타이머가 있다.
    공통 골격(기본 정보 폼·저장 다이얼로그·Raw Data)은 BaseWizard에 있고 여기선 스텝 입력만 구현한다.
    BaseWizard 기본 설정(item_col=test_item, tester_col=test_by 등)이 기능 테스트와 같아 그대로 쓴다."""

    def __init__(self, cfg: dict) -> None:
        super().__init__(cfg)
        self.steps = cfg["steps"]
        self.total = len(self.steps)
        self.form = cfg.get("form")  # Raw Data 공식 양식 다운로드용(없으면 버튼 비노출)

    # ── BaseWizard 훅 ─────────────────────────────────────────
    def _load_df(self):
        return load_records()

    def _delete_one(self, serial: str) -> None:
        delete_serial(serial)

    def _build_summary(self, values: dict) -> list[dict]:
        return summary_records(self.steps, values)

    def _build_rows(self, base: dict, values: dict) -> list:
        return [(base["serial"], i + 1, base["test_datetime"], base["tested_by"], values[i])
                for i in range(self.total)]

    def _insert(self, rows: list) -> None:
        insert_records(rows)

    def _init_step(self) -> None:
        self._set("val", "")  # 첫 스텝 입력칸을 빈값으로

    def _reset(self) -> None:
        for name in ("base", "step", "values", "val", "confirm_save", "confirm_move"):
            st.session_state.pop(self._key(name), None)
        # Serial 입력칸은 비워 다음 테스트를 새 번호로 시작한다(날짜·담당자는 유지).
        st.session_state.pop(self._key("in_serial"), None)
        # 스텝별 타이머 상태도 초기화(재진입 시 처음부터).
        for i in range(self.total):
            st.session_state.pop(self._key(f"timer_start_{i}"), None)

    def _download_button(self, view) -> None:
        if not self.form:  # 양식이 없는 보드(Controller 등)는 버튼 비노출
            return
        st.download_button(
            ":material/download: Download XLSX",
            data=build_filled_form(self.form["file"], self.form["sheet"],
                                   self.form["serial_col"], self.prefix, self.total, view),
            file_name=f"{self.form['file'].removesuffix('.xlsx')}_{datetime.now():%y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=view.empty, width="stretch", key=self._key("dl_form"),
        )

    # ── 위자드 콜백 ───────────────────────────────────────────
    # 버튼은 st.rerun() 대신 on_click 콜백으로 처리한다. 콜백은 재실행 '전'에 돌아 rerun이 한 번만
    # 일어나므로, 폼 제출 직후 "Missing Submit Button" 깜빡임이 없다.
    def _advance_step(self) -> None:
        """다음 스텝으로. 타이머 진행 중이면 곧장 이동하지 않고 이동 확인 모달 플래그만 세운다.
        (마지막 스텝의 '저장'은 별도 저장 확인 모달이 있으므로 이동 확인 대상이 아니다.)"""
        step = self._get("step")
        if step < self.total - 1 and self._timer_running(step):
            self._set("confirm_move", "next")  # st.dialog는 본문에서 열어야 하므로 플래그만 세운다
        else:
            self._do_advance()

    def _prev_step(self) -> None:
        step = self._get("step")
        if step > 0 and self._timer_running(step):
            self._set("confirm_move", "prev")
        else:
            self._do_prev()

    def _do_advance(self) -> None:
        """현재 값을 저장하고 다음 스텝으로(마지막이면 저장 확인 다이얼로그 요청). 이동 시 타이머는 초기화."""
        step = self._get("step")
        values = self._get("values")
        values[step] = self._get("val")
        self._clear_timer(step)
        if step >= self.total - 1:
            # st.dialog는 콜백이 아니라 본문에서 호출해야 열리므로 플래그만 세운다(본문이 연다).
            self._set("confirm_save", True)
        else:
            self._set("step", step + 1)
            # 다음 스텝의 저장값(없으면 빈값)으로 입력칸을 갈아끼운다(key 고정이라 위젯 재생성 없음).
            self._set("val", values.get(step + 1, ""))

    def _do_prev(self) -> None:
        step = self._get("step")
        if step > 0:
            values = self._get("values")
            values[step] = self._get("val")
            self._clear_timer(step)
            self._set("step", step - 1)
            self._set("val", values.get(step - 1, ""))

    def _confirm_move_dialog(self, direction: str) -> None:
        """타이머 진행 중 스텝 이동 확인 모달. 확인 시 이동(+타이머 초기화), 취소 시 현재 스텝 유지."""
        confirm_dialog(
            "스텝 이동 확인",
            body="타이머가 진행 중입니다. 이동하면 타이머가 **초기화**됩니다.\n\n정말 이동하시겠습니까?",
            ok_label=":material/arrow_forward: 이동",
            on_confirm=self._do_advance if direction == "next" else self._do_prev,
        )

    def _start_timer(self, step: int) -> None:
        """'타이머 시작/재시작' 콜백 — 시작 시각만 기록한다(카운트다운은 브라우저 CSS가 진행)."""
        self._set(f"timer_start_{step}", time.monotonic())

    def _timer_running(self, step: int) -> bool:
        """현재 스텝에 아직 끝나지 않은(진행 중) 타이머가 켜져 있으면 True."""
        seconds = self.steps[step].get("timer")
        start = self._get(f"timer_start_{step}")
        if not seconds or start is None:
            return False
        return time.monotonic() - start < seconds

    def _clear_timer(self, step: int) -> None:
        """해당 스텝의 타이머 상태를 지운다(이동 시 항상 초기화 → 재진입 시 처음부터)."""
        st.session_state.pop(self._key(f"timer_start_{step}"), None)

    def _render_timer(self, step: int, seconds: float) -> None:
        """측정 전 대기를 돕는 안내용 카운트다운(입력·진행은 막지 않음).
        카운트다운은 서버 재실행이 아니라 브라우저 CSS 애니메이션으로 진행한다. run_every로 0.1초마다
        서버를 왕복하던 기존 방식은 망 지연(특히 터널)에서 재실행이 몰렸다 멈췄다 하며 숫자가
        '15→14→(정체)→7'처럼 건너뛰었다 — CSS 방식은 왕복이 없어 지연과 무관하게 매끄럽다.
        완료 메시지(st.success)는 서버 요소라, 끝나는 순간 '한 번'만 rerun해 띄운다(폴링 아님)."""
        start_key = self._key(f"timer_start_{step}")
        started = start_key in st.session_state
        if started:
            elapsed = time.monotonic() - st.session_state[start_key]
            if elapsed >= seconds:
                st.success(f":material/timer: {seconds:g}초 대기 완료")
            else:
                self._render_countdown(step, seconds, elapsed)
                self._schedule_complete(start_key, seconds, seconds - elapsed)

        label = ":material/refresh: 타이머 재시작" if started else f":material/timer: 타이머 시작 ({seconds:g}초)"
        st.button(label, key=self._key(f"timer_btn_{step}"), width="stretch",
                  on_click=self._start_timer, args=(step,))

    def _schedule_complete(self, start_key: str, seconds: float, remaining: float) -> None:
        """카운트다운이 끝나는 순간 딱 한 번 rerun해 완료 메시지(st.success)를 띄운다.
        run_every=남은시간이라 대기 중엔 서버를 안 치고, 완료 시점에 1회 깨어나 전체 rerun을 건다.
        그 뒤엔 elapsed>=seconds 분기로 들어가 이 fragment를 다시 만들지 않으므로 폴링이 되지 않는다."""
        @st.fragment(run_every=max(0.1, remaining))
        def _fire() -> None:
            if time.monotonic() - st.session_state.get(start_key, 0) >= seconds:
                st.rerun()  # 완료 → 전체 rerun → _render_timer가 st.success 분기로 진입

        _fire()

    def _render_countdown(self, step: int, seconds: float, elapsed: float) -> None:
        """남은 시간을 브라우저에서 CSS로 카운트다운한다(서버 왕복 없음).
        숫자(n‥0)를 세로로 쌓아 steps()로 1초마다 한 칸씩 밀어 올려 보여 주고, 막대는 width로 채운다.
        animation-delay에 -elapsed를 줘, rerun으로 HTML이 다시 그려져도 이미 흐른 만큼 건너뛴 지점부터
        이어 보여 준다. (@property는 st.html이 제거하므로 @keyframes+transform만 사용한다.)
        https://docs.streamlit.io/develop/api-reference/utilities/st.html"""
        n = math.ceil(seconds)              # 시작 표시 숫자 = 올림(기존 int(remaining)+1과 동일)
        name = f"cd-{self.prefix}-{step}"   # 보드·스텝별 고유 식별자(클래스·keyframes 공용)
        delay, dur = f"{-elapsed:.2f}s", f"{seconds:g}s"
        nums = "".join(f"<span>{k}</span>" for k in range(n, -1, -1))  # n, n-1, ..., 1, 0
        st.html(f"""
        <div class="{name}">
          <div class="lbl">남은 시간:
              <span class="win"><span class="strip">{nums}</span></span>초</div>
          <div class="track"><div class="fill"></div></div>
        </div>
        <style>
        @keyframes {name}-roll {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-{n}em); }} }}
        @keyframes {name}-bar  {{ from {{ width: 0%; }} to {{ width: 100%; }} }}
        .{name} .win {{ display: inline-block; height: 1em; line-height: 1em; overflow: hidden;
                        vertical-align: -0.15em; }}
        .{name} .strip {{ display: flex; flex-direction: column; align-items: flex-end;
                          animation: {name}-roll {dur} steps({n}) {delay} forwards; }}
        .{name} .strip > span {{ height: 1em; line-height: 1em; }}
        .{name} .track {{ height: 0.5rem; background: rgba(128,128,128,0.25);
                          border-radius: 0.25rem; overflow: hidden; margin-top: 0.35rem; }}
        .{name} .fill {{ height: 100%; background: #3893fe;
                         animation: {name}-bar {dur} linear {delay} forwards; }}
        </style>
        """)

    # ── 스텝 입력 화면 ────────────────────────────────────────
    def _render_step_wizard(self) -> None:
        base = self._get("base")
        step = self._get("step")
        spec = self.steps[step]
        lo, hi, unit = spec["min"], spec["max"], spec["unit"]
        has_range = lo is not None or hi is not None
        is_last = step == self.total - 1

        # 저장 확인 요청이 있으면 모달을 연다(본문에서 호출해야 열림). 플래그는 '즉시 소비'해 한 번만 연다 —
        # st.tabs는 매 rerun에 모든 탭 코드를 실행하므로 그대로 두면 다른 탭 rerun에도 모달이 다시 뜬다.
        if self._get("confirm_save"):
            self._set("confirm_save", False)
            self._confirm_save_dialog()

        # 타이머 진행 중 스텝 이동 요청이 있으면 이동 확인 모달을 연다(확인 시 이동+타이머 초기화).
        if self._get("confirm_move"):
            direction = self._get("confirm_move")
            self._set("confirm_move", None)
            self._confirm_move_dialog(direction)

        with st.container(border=True):
            self._render_cancel_header(base)
            st.progress(step / self.total, text=f"{step}/{self.total} 완료")
            st.markdown(f"#### {spec['description']}")

            if has_range:
                lo_txt = "−∞" if lo is None else lo
                hi_txt = "∞" if hi is None else hi
                st.caption(f"허용 범위: {lo_txt} ~ {hi_txt} {unit}".rstrip())

            if spec.get("timer"):  # 대기 시간이 정의된 스텝에만 카운트다운(안내용 · 폼 밖)
                self._render_timer(step, spec["timer"])

            next_label = ":material/save: 저장" if is_last else "다음 :material/arrow_forward:"
            # 조회 전용(viewer)은 스텝은 둘러보되 마지막 '저장'만 막는다(DB 쓰기는 저장 다이얼로그에서만 일어남).
            save_blocked = is_last and not can_edit()
            nav_key, val_key = self._key("nav"), self._key("val")
            next_key, prev_key = self._key("submit_next"), self._key("submit_prev")
            # '다음/저장'·'이전'을 모두 form_submit_button으로 폼 안에 둔다. 폼 위젯 값은 '제출' 시에만
            # session_state에 커밋되므로, '이전'을 폼 밖 버튼으로 두면 방금 입력한 값이 유실된다(실측 확인).
            # '다음'을 먼저 정의하면 submit이 2개여도 Enter는 항상 '다음'으로 간다(Enter=첫 submit).
            # 폼 key에 step을 포함해 스텝 이동마다 remount → 미제출 입력 버퍼가 폐기되어 값 누수가 차단된다.
            with st.container(key=nav_key):
                with st.form(self._key(f"step_form_{step}"), border=False, clear_on_submit=False):
                    st.text_input(f"측정값 ({unit})" if unit else "측정값", key=val_key)
                    st.form_submit_button(next_label, type="primary", width="stretch",
                                          key=next_key, on_click=self._advance_step,
                                          disabled=save_blocked,
                                          help="조회 전용 계정은 저장할 수 없습니다." if save_blocked else None)
                    if step > 0:
                        st.form_submit_button(":material/arrow_back: 이전", width="stretch",
                                              key=prev_key, on_click=self._prev_step)
            # 폼/내부 블록을 display:contents로 평탄화 → 입력칸(1행 전체) / 이전·다음(2행 좌우).
            st.html(f"""<style>
            .st-key-{nav_key} {{ display:flex; flex-flow:row wrap; gap:0.5rem; }}
            .st-key-{nav_key} > [data-testid="stLayoutWrapper"] {{ display:contents; }}
            .st-key-{nav_key} [data-testid="stForm"] {{ display:contents; padding:0; border:0; }}
            .st-key-{nav_key} [data-testid="stForm"] > [data-testid="stVerticalBlock"] {{ display:contents; }}
            .st-key-{val_key} {{ order:0; flex:0 0 100%; }}
            .st-key-{prev_key} {{ order:1; flex:1 1 0; min-width:0; }}
            .st-key-{next_key} {{ order:2; flex:1 1 0; min-width:0; }}
            </style>""")


# ── 탭 구성 ───────────────────────────────────────────────
# steps가 채워진 보드만 위자드를 노출하고, 비어 있으면 "준비 중"으로 표시한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = BoardWizard(BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        if not wizard.total:
            st.info("준비 중입니다.")
        else:
            # 위자드(TEST STEP)는 누구나 둘러볼 수 있고, 저장만 마지막 스텝에서 can_edit로 막는다.
            wizard.render_input()
            st.divider()
            wizard.render_records()
