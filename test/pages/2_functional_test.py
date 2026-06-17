import time

import streamlit as st

from constants import BOARD_CONFIG, BOARD_LABELS
from database import delete_serial, insert_records, load_records

# 타이머 진행바 갱신 주기(초). 작을수록 부드럽지만 fragment 재실행이 잦아진다.
# 재실행 왕복 한계로 실질 하한은 ~0.1s (그보다 작으면 오히려 끊긴다).
TIMER_REFRESH_SEC = 0.1

role = st.session_state.get("role", "viewer")
can_edit = role in ("admin", "editor")

st.title("Functional Test")
st.caption('CG PCBA 5종에 대한 "기능 테스트"를 진행합니다.')


class BoardWizard:
    """보드 한 종의 기능 테스트 입력 위자드 + 조회 화면.

    보드별 진행 상태는 prefix로 네임스페이스한 세션 키에 보관해 탭 간 충돌을 막는다.
      {p}_base   : {"serial", "test_date", "tested_by"} (기본 정보 확인 시 생성 → 위자드 진입)
      {p}_step   : 현재 스텝 인덱스 (0 ~ total)
      {p}_values : {스텝 인덱스: 측정값}
      {p}_val    : 현재 측정값 입력칸의 값(위젯 key). 스텝마다 콜백에서 갈아끼운다.
    위젯 key도 모두 prefix로 분리해 여러 보드가 동시에 렌더돼도 충돌하지 않는다.
    """

    def __init__(self, cfg: dict) -> None:
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]
        self.steps = cfg["steps"]
        self.total = len(self.steps)
        # Serial 입력 예시 (placeholder·에러 문구 공용): 예) H0021
        self.example = f"{self.prefix}{21:0{self.digits}d}"

    # ── 세션 키 (prefix 네임스페이스) ─────────────────────────
    def _key(self, name: str) -> str:
        return f"{self.prefix}_{name}"

    # 세션 값 읽기/쓰기 헬퍼. st.session_state[self._key(...)] 반복을 줄인다.
    # (위젯 key 인자는 식별자이므로 _key()를 그대로 쓰고, 여기선 값 접근만 다룬다.)
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

    # ── 위자드 콜백 ───────────────────────────────────────────
    # 버튼 처리는 st.rerun() 대신 on_click 콜백으로 한다. 콜백은 스크립트 재실행 '전'에
    # 실행되어 rerun이 한 번만 깔끔히 돌기 때문에, 폼 제출 직후 이중 rerun으로 폼이
    # 허물어지며 "Missing Submit Button"이 깜빡이는 현상이 사라진다.
    def _advance_step(self) -> None:
        """현재 스텝 값을 저장하고 다음 스텝으로(마지막이면 전체 일괄 저장)."""
        step = self._get("step")
        values = self._get("values")
        values[step] = self._get("val")
        if step >= self.total - 1:
            base = self._get("base")
            rows = [
                (base["serial"], i + 1, base["test_date"], base["tested_by"], values[i])
                for i in range(self.total)
            ]
            insert_records(rows, st.user.email)
            # 저장 알림은 토스트로(자동 사라짐). 콜백에서 호출해도 재실행 후 표시된다.
            st.toast(f"**{base['serial']}** 의 데이터가 저장되었습니다.", icon="💾")
            # 완료 화면 없이 곧바로 기본 정보(Serial·날짜·담당자) 입력 화면으로 돌아간다.
            self._reset()
        else:
            self._set("step", step + 1)
            # 다음 스텝의 저장값(없으면 빈값)으로 입력칸을 갈아끼운다. key가 고정이라
            # 위젯 재생성 없이 값만 바뀌므로 폼이 안정적으로 유지된다.
            self._set("val", values.get(step + 1, ""))

    def _prev_step(self) -> None:
        step = self._get("step")
        if step > 0:
            self._get("values")[step] = self._get("val")
            self._set("step", step - 1)
            self._set("val", self._get("values").get(step - 1, ""))

    def _reset(self) -> None:
        for name in ("base", "step", "values", "val"):
            st.session_state.pop(self._key(name), None)
        # Serial 입력칸은 비워 다음 테스트를 새 번호로 시작하게 한다.
        # (날짜·담당자는 보통 동일하므로 유지)
        st.session_state.pop(self._key("in_serial"), None)
        # 스텝별 타이머 상태도 함께 초기화 (재진입 시 처음부터)
        for i in range(self.total):
            st.session_state.pop(self._key(f"timer_deadline_{i}"), None)
            st.session_state.pop(self._key(f"timer_done_{i}"), None)

    def _start_timer(self, step: int, seconds: float) -> None:
        """'타이머 시작/재시작' 콜백 — deadline을 새로 잡고 완료 플래그를 내린다."""
        self._set(f"timer_deadline_{step}", time.monotonic() + seconds)
        self._set(f"timer_done_{step}", False)

    # ── 입력 폼 ───────────────────────────────────────────────
    def render_input(self) -> None:
        """① 기본 정보(Serial·날짜·담당자) 확인 → ② 스텝 측정값 입력 → 일괄 저장."""
        if self._get("base") is None:
            self._render_base_form()
        else:
            self._render_step_wizard()

    def _render_base_form(self) -> None:
        # Serial 등 입력칸에서 Enter → '확인'으로 제출되게 폼으로 묶는다(폼의 enter_to_submit이
        # 커서가 있어도 Enter를 잡아주는 유일한 방법). submit 버튼이 '확인' 하나뿐이라 Enter는
        # 확인으로 간다. (과거 "Missing Submit Button" 깜빡임은 config.toml의 fastReruns=false로 방지)
        with st.form(self._key("base_form"), border=True, clear_on_submit=False):
            col1, col2, col3 = st.columns(3)
            serial = col1.text_input("Serial 번호", placeholder=f"예시: 21 or {self.example}",
                                     key=self._key("in_serial"))
            test_date = col2.date_input("날짜", key=self._key("in_date"))
            tested_by = col3.text_input("진행자", value=st.user.name, key=self._key("in_by"))
            confirmed = st.form_submit_button("확인", type="primary", width="stretch",
                                              key=self._key("confirm"))

        if not confirmed:
            return

        serial_norm = self._normalize_serial(serial)
        if serial_norm is None:
            st.error(f"Serial 번호는 '{self.prefix} + 숫자 {self.digits}자리' 형식입니다. "
                     f"숫자만 입력해도 됩니다 (예: 21 → {self.example}).")
            return
        if not tested_by.strip():
            st.error("테스트 담당자는 필수 항목입니다.")
            return

        # 이미 테스트된 Serial이면 경고하고 진입을 막는다(중복 저장 방지).
        existing = load_records(st.user.email, role)["serial"]
        if serial_norm in set(existing):
            st.toast("이미 테스트를 완료하였습니다.", icon="⚠️")
            return

        self._set("base", {
            "serial": serial_norm,
            "test_date": test_date.isoformat(),
            "tested_by": tested_by.strip(),
        })
        self._set("step", 0)
        self._set("values", {})
        self._set("val", "")
        st.rerun()

    def _render_timer(self, step: int, seconds: float) -> None:
        """측정 전 대기를 돕는 안내용 카운트다운. '타이머 시작' 클릭 시 시작하며
        입력·진행을 막지 않는다. run_every를 미리 계산해 0이 되면 None으로 멈춘다.
        https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment"""
        deadline_key = self._key(f"timer_deadline_{step}")
        done_key = self._key(f"timer_done_{step}")
        started = deadline_key in st.session_state

        if started:
            running = not st.session_state.get(done_key)

            @st.fragment(run_every=TIMER_REFRESH_SEC if running else None)  # 완료 시 None → 자동 정지
            def _tick() -> None:
                if st.session_state.get(done_key):
                    st.success(f":material/timer: {seconds}초 대기 완료")
                    return
                remaining = st.session_state[deadline_key] - time.monotonic()
                if remaining <= 0:
                    st.session_state[done_key] = True
                    st.rerun()  # 전체 rerun → run_every=None으로 재데코레이트되어 멈춤
                st.progress(
                    max(0.0, min(1.0, 1 - remaining / seconds)),
                    text=f":material/timer: 남은 시간 {int(remaining) + 1}초",
                )

            _tick()

        # 상태만 바꾸는 버튼이므로 인라인 st.rerun() 대신 on_click 콜백을 쓴다(파일 공통 규칙).
        label = ":material/refresh: 타이머 재시작" if started else f":material/timer: 타이머 시작 ({seconds}초)"
        st.button(label, key=self._key(f"timer_btn_{step}"), width="stretch",
                  on_click=self._start_timer, args=(step, seconds))

    def _render_step_wizard(self) -> None:
        base = self._get("base")
        step = self._get("step")
        spec = self.steps[step]
        lo, hi, unit = spec["min"], spec["max"], spec["unit"]
        has_range = lo is not None or hi is not None
        is_last = step == self.total - 1

        # 기본 정보 폼과 동일한 테두리 박스 안에 스텝 입력을 배치한다.
        with st.container(border=True):
            # 캡션(좌) + 취소 버튼(우상단). 취소는 상태만 되돌리므로 폼 밖 일반 버튼.
            info_col, cancel_col = st.columns([4, 1], vertical_alignment="center")
            info_col.caption(f"**{base['serial']}**  ·  {base['test_date']}  ·  {base['tested_by']}")
            cancel_col.button(":material/close: 취소", width="stretch",
                              on_click=self._reset, key=self._key("cancel"))
            st.progress(step / self.total, text=f"{step}/{self.total} 완료")
            st.markdown(f"#### {spec['description']}")

            if has_range:
                lo_txt = "−∞" if lo is None else lo
                hi_txt = "∞" if hi is None else hi
                st.caption(f"허용 범위: {lo_txt} ~ {hi_txt} {unit}".rstrip())

            # 측정 전 대기 시간이 정의된 스텝에만 카운트다운 표시 (안내용 · 폼 밖)
            if spec.get("timer"):
                self._render_timer(step, spec["timer"])

            # 측정값 입력칸에서 Enter → 다음으로 넘기려면 폼으로 묶어야 한다(폼의 enter_to_submit이
            # 커서가 있어도 Enter를 잡아주는 유일한 방법). 단 Enter는 '레이아웃상 가장 왼쪽'
            # submit 버튼을 누르므로, DOM에서는 '다음'을 왼쪽(col_next)에 두어 Enter 대상으로
            # 잡고, 화면에는 이전(좌)/다음(우)로 보이도록 아래 CSS(row-reverse)로 열 순서만
            # 뒤집는다. enter_to_submit은 서버측 요소 순서로 계산돼 CSS 반전의 영향을 받지 않는다.
            with st.form(self._key("step_form"), border=False, clear_on_submit=False):
                # key를 고정("{p}_val")해 스텝이 바뀌어도 위젯이 재생성되지 않게 한다.
                # (값은 _advance_step/_prev_step 콜백에서 세션 상태로 관리)
                st.text_input(f"측정값 ({unit})" if unit else "측정값", key=self._key("val"))

                next_label = ":material/save: 저장" if is_last else "다음 :material/arrow_forward:"
                if step > 0:
                    # st.container(key=...)는 'st-key-{key}' CSS 클래스를 만든다. 이 클래스로
                    # 이 행의 열 순서만 row-reverse 해 표시 순서(이전 좌/다음 우)를 맞춘다.
                    nav_key = self._key("nav")
                    with st.container(key=nav_key):
                        col_next, col_prev = st.columns(2)  # DOM: 다음(좌=Enter 대상) → 이전
                        col_next.form_submit_button(next_label, type="primary", width="stretch",
                                                    on_click=self._advance_step)
                        col_prev.form_submit_button(":material/arrow_back: 이전",
                                                    width="stretch", on_click=self._prev_step)
                    st.html(f"<style>.st-key-{nav_key} "
                            f'[data-testid="stHorizontalBlock"]{{flex-direction:row-reverse}}</style>')
                else:
                    # 첫 스텝: 이전 없음 → 다음만 1열(full-width). 단독이라 Enter도 자연히 다음.
                    st.form_submit_button(next_label, type="primary", width="stretch",
                                          on_click=self._advance_step)

    # ── 데이터 조회 (Raw Data) ────────────────────────────────
    def render_records(self) -> None:
        df = load_records(st.user.email, role)
        st.subheader("Raw Data")

        # 보드 접두사로 시작하는 Serial 행만 표시한다.
        # (정렬은 load_records에서 serial + test_item 숫자 오름차순으로 이미 적용됨)
        df = df[df["serial"].str.startswith(self.prefix)]

        if df.empty:
            st.info("아직 저장된 데이터가 없습니다.")
            return

        col1, col2 = st.columns(2)
        col1.metric("고유 Serial 수", df["serial"].nunique())
        col2.metric("고유 Test Item 수", df["test_item"].nunique())

        # ── Serial 필터 (모든 권한 공용) ──────────────────────────
        # '전체' 선택 시 필터 해제, 특정 Serial 선택 시 그 Serial 행만 표시한다.
        ALL = "전체"
        options = [ALL] + df["serial"].unique().tolist()

        # 삭제 확인은 Modal Dialog로 받는다. 다이얼로그 안에서 st.rerun()을 호출하면
        # 다이얼로그가 닫히며 페이지가 재실행된다(취소 = 변경 없이 닫기).
        @st.dialog("데이터 삭제 확인")
        def _confirm_delete(serial: str) -> None:
            st.markdown(f"**{serial}** 의 모든 데이터를 삭제합니다.")
            ok_col, cancel_col = st.columns(2)
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("del_ok")):
                delete_serial(serial)
                self._set("del_msg", f"**{serial}** 의 데이터가 삭제되었습니다.")
                st.rerun()
            if cancel_col.button(":material/close: 취소", width="stretch", key=self._key("del_cancel")):
                st.rerun()

        # 직전 실행에서 삭제가 완료됐다면 다이얼로그가 닫힌 뒤 토스트로 알린다.
        msg = st.session_state.pop(self._key("del_msg"), None)
        if msg:
            st.toast(msg, icon="🗑️")

        if role == "admin":
            # 관리자만 선택한 Serial을 삭제할 수 있다. (우측 삭제 버튼)
            # vertical_alignment="bottom" 으로 selectbox(라벨 포함)와 버튼 하단을 맞춘다.
            sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
            selected = sel_col.selectbox("Serial 번호 선택", options, key=self._key("filter_serial"))
            if btn_col.button(":material/delete: 삭제", type="primary", width="stretch",
                              disabled=selected == ALL, key=self._key("del_btn")):
                _confirm_delete(selected)
        else:
            selected = st.selectbox("Serial 번호 선택", options, key=self._key("filter_serial"))

        # 선택된 Serial로 테이블을 필터링한다. (조회 전용 — st.dataframe)
        view = df if selected == ALL else df[df["serial"] == selected]
        st.dataframe(view, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
# STEPS가 채워진 보드만 위자드를 노출하고, 비어 있으면 "준비 중"으로 표시한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = BoardWizard(BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        if not wizard.total:
            st.info("준비 중입니다.")
        else:
            if can_edit:
                wizard.render_input()
            else:
                st.info("조회 전용 계정입니다. 데이터를 추가하려면 관리자에게 권한을 요청하세요.")
            st.divider()
            wizard.render_records()
