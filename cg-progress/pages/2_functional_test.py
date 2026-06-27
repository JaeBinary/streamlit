import time
from datetime import datetime

import pandas as pd
import streamlit as st

from constants import BOARD_CONFIG, BOARD_LABELS, summary_records
from database import delete_serial, insert_records, load_records, user_names
from export import build_filled_form

# 타이머 진행바 갱신 주기(초). 재실행 왕복 한계로 실질 하한은 ~0.1s.
TIMER_REFRESH_SEC = 0.1

role = st.session_state.get("role", "viewer")
can_edit = role in ("admin", "editor")

st.title("Functional Test")
st.caption('CG PCBA 5종에 대한 "기능 테스트"를 진행합니다.')


class BoardWizard:
    """보드 한 종의 기능 테스트 입력 위자드 + 조회 화면.

    진행 상태는 prefix로 네임스페이스한 세션 키에 보관해 탭 간 충돌을 막는다.
      {p}_base   : {"serial", "test_datetime", "tested_by"(oid), "tested_by_name"(표시용)} (기본 정보 확인 시 생성)
      {p}_step   : 현재 스텝 인덱스 (0 ~ total)
      {p}_values : {스텝 인덱스: 측정값}
      {p}_val    : 현재 입력칸 값(위젯 key). 스텝마다 콜백에서 갈아끼운다.
    위젯 key도 모두 prefix로 분리해 여러 보드가 동시에 렌더돼도 충돌하지 않는다.
    """

    def __init__(self, cfg: dict) -> None:
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]
        self.steps = cfg["steps"]
        self.total = len(self.steps)
        # Raw Data 공식 양식 다운로드용 매핑(없으면 버튼 비노출)
        self.form = cfg.get("form")
        # Serial 입력 예시 (placeholder·에러 문구 공용): 예) H0021
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

    # ── 위자드 콜백 ───────────────────────────────────────────
    # 버튼은 st.rerun() 대신 on_click 콜백으로 처리한다. 콜백은 재실행 '전'에 실행돼
    # rerun이 한 번만 돌므로, 폼 제출 직후 "Missing Submit Button" 깜빡임이 없다.
    def _advance_step(self) -> None:
        """현재 값을 저장하고 다음 스텝으로(마지막이면 저장 확인 다이얼로그 요청)."""
        step = self._get("step")
        values = self._get("values")
        values[step] = self._get("val")
        if step >= self.total - 1:
            # 마지막 스텝: 곧바로 저장하지 않고 확인 다이얼로그를 띄우도록 플래그만 세운다.
            # st.dialog는 콜백이 아니라 스크립트 본문에서 호출해야 모달이 열리므로,
            # 실제 저장은 _render_step_wizard가 여는 다이얼로그에서 처리한다.
            self._set("confirm_save", True)
        else:
            self._set("step", step + 1)
            # 다음 스텝의 저장값(없으면 빈값)으로 입력칸을 갈아끼운다. key가 고정이라
            # 위젯 재생성 없이 값만 바뀌어 폼이 안정적으로 유지된다.
            self._set("val", values.get(step + 1, ""))

    def _prev_step(self) -> None:
        step = self._get("step")
        if step > 0:
            values = self._get("values")
            values[step] = self._get("val")
            self._set("step", step - 1)
            self._set("val", values.get(step - 1, ""))

    def _reset(self) -> None:
        for name in ("base", "step", "values", "val", "confirm_save"):
            st.session_state.pop(self._key(name), None)
        # Serial 입력칸은 비워 다음 테스트를 새 번호로 시작한다(날짜·담당자는 유지).
        st.session_state.pop(self._key("in_serial"), None)
        # 스텝별 타이머 상태도 초기화 (재진입 시 처음부터)
        for i in range(self.total):
            st.session_state.pop(self._key(f"timer_deadline_{i}"), None)
            st.session_state.pop(self._key(f"timer_done_{i}"), None)

    def _start_timer(self, step: int, seconds: float) -> None:
        """'타이머 시작/재시작' 콜백 — deadline을 새로 잡고 완료 플래그를 내린다."""
        self._set(f"timer_deadline_{step}", time.monotonic() + seconds)
        self._set(f"timer_done_{step}", False)

    # ── 저장 확인 다이얼로그 ──────────────────────────────────
    def _confirm_save_dialog(self) -> None:
        """입력값을 모아 보여주고 최종 저장/취소를 받는 모달. confirm_save 플래그가 있을 때 연다."""
        base = self._get("base")
        values = self._get("values")

        @st.dialog("데이터 확인")
        def _dlg() -> None:
            st.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
            st.markdown("아래 측정값을 저장합니다.")
            st.dataframe(pd.DataFrame(summary_records(self.steps, values)),
                         width="stretch", hide_index=True)
            # 확인용 읽기 전용 표라 dataframe 툴바(검색·다운로드·열 표시/숨김)는 불필요하다.
            # 또한 모달을 Enter(키보드)로 열면 그 툴바 버튼에 hover/focus가 걸려
            # 'Show/hide columns' 툴팁이 뜨므로(마우스 클릭으로 열 땐 안 뜸) 다이얼로그 내 툴바를 숨긴다.
            st.html('<style>[role="dialog"] [data-testid="stElementToolbar"]{display:none}</style>')

            cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 확인/삭제 우측
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("save_ok")):
                rows = [
                    (base["serial"], i + 1, base["test_datetime"], base["tested_by"], values[i])
                    for i in range(self.total)
                ]
                insert_records(rows)
                # rerun 후에도 유지되는 토스트로 알리려 메시지를 남기고(다이얼로그가 닫힌 뒤 표시),
                # _reset이 confirm_save까지 비운 뒤 기본 정보 화면으로 돌아간다.
                # 저장 시점엔 '검수 중'이며, 관리자가 검수 리스트에서 승인해야 최종 저장된다.
                self._set("save_msg", f"**{base['serial']}** 저장됨 · 관리자 검수 대기 중")
                self._reset()
                st.rerun()
            if cancel_col.button(":material/close: 취소", width="stretch",
                                 key=self._key("save_cancel")):
                # 모달만 닫고 마지막 스텝에 그대로 머문다(confirm_save는 열 때 이미 소비됨).
                st.rerun()

        _dlg()

    # ── 입력 폼 ───────────────────────────────────────────────
    def render_input(self) -> None:
        """① 기본 정보(Serial·날짜·담당자) 확인 → ② 스텝 측정값 입력 → 저장 확인 → 저장."""
        # 직전 실행에서 저장됐다면 다이얼로그가 닫힌 뒤 토스트로 알린다.
        msg = st.session_state.pop(self._key("save_msg"), None)
        if msg:
            st.toast(msg, icon="💾")

        if self._get("base") is None:
            self._render_base_form()
        else:
            self._render_step_wizard()

    def _render_base_form(self) -> None:
        # Enter → '확인' 제출이 되도록 폼으로 묶는다(폼 enter_to_submit이 커서 위치와
        # 무관하게 Enter를 잡아준다). submit이 '확인' 하나뿐이라 Enter는 확인으로 간다.
        with st.form(self._key("base_form"), border=True, clear_on_submit=False):
            col1, col2, col3 = st.columns(3)
            serial = col1.text_input("Serial 번호", placeholder=f"예시: 21 or {self.example}",
                                     key=self._key("in_serial"))
            # 날짜는 오늘로, 진행자는 로그인 사용자 이름으로 자동 고정한다(비활성·표시용).
            # 저장은 이름이 아니라 불변 oid로 하므로(아래 base) AD에서 이름이 바뀌어도
            # 과거 기록과의 매핑이 끊기지 않는다. 조회 화면에선 oid→현재 이름으로 변환해 보여준다.
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

        # 이미 테스트된 Serial이면 진입을 막는다(중복 저장 방지). 검수 중·승인 모두 포함해 막는다.
        existing = load_records()["serial_number"]
        if serial_norm in set(existing):
            st.toast("이미 테스트를 완료하였습니다.", icon="⚠️")
            return

        self._set("base", {
            "serial": serial_norm,
            # 값은 시각까지 저장(test_datetime), 표시는 호출부에서 date만 잘라 쓴다.
            # 날짜칸(비활성=오늘)에 확인 시점의 시각을 합쳐 'YYYY-MM-DD HH:MM:SS'로 만든다.
            "test_datetime": datetime.combine(test_date, datetime.now().time())
                                     .strftime("%Y-%m-%d %H:%M:%S"),
            "tested_by": st.user.oid,        # DB 저장용 — 불변 oid
            "tested_by_name": st.user.name,  # 화면 표시용 — 현재 로그인 이름
        })
        self._set("step", 0)
        self._set("values", {})
        self._set("val", "")
        st.rerun()

    def _render_timer(self, step: int, seconds: float) -> None:
        """측정 전 대기를 돕는 안내용 카운트다운(입력·진행은 막지 않음).
        run_every를 미리 계산해 완료 시 None으로 자동 정지한다.
        https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment"""
        deadline_key = self._key(f"timer_deadline_{step}")
        done_key = self._key(f"timer_done_{step}")
        started = deadline_key in st.session_state

        if started:
            running = not st.session_state.get(done_key)

            @st.fragment(run_every=TIMER_REFRESH_SEC if running else None)  # 완료 시 None → 정지
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

        # 상태만 바꾸는 버튼 → on_click 콜백(파일 공통 규칙).
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

        # 저장 확인 요청이 있으면 모달을 연다(콜백이 아닌 본문에서 호출해야 모달이 열림).
        # 플래그는 '즉시 소비'해 한 번만 연다. 그대로 두면 st.tabs 특성상(모든 탭의 코드가 매
        # rerun 실행됨) 다른 보드 탭에서 일어난 rerun에도 이 보드의 모달이 다시 열려, 사용자가
        # 보고 있는 엉뚱한 탭 위에 뜬다. 모달을 닫거나(취소·X) 확인하면 흐름이 끝나므로 한 번 열기로 충분.
        if self._get("confirm_save"):
            self._set("confirm_save", False)
            self._confirm_save_dialog()

        with st.container(border=True):
            # 캡션(좌) + 취소 버튼(우상단). 취소는 상태만 되돌리므로 폼 밖 일반 버튼.
            # 아이콘만 남긴 tertiary 버튼을 키 있는 컨테이너에 담고 align-items:flex-end로
            # 컬럼 우측 끝에 붙인다(파일 공통 CSS 방식). 동작은 help 툴팁으로 안내.
            info_col, cancel_col = st.columns([9, 1], vertical_alignment="center")
            info_col.caption(f"**{base['serial']}**  ·  {base['test_datetime'][:10]}  ·  {base['tested_by_name']}")
            cancel_key = self._key("cancel_box")
            with cancel_col.container(key=cancel_key):
                st.button(":material/close:", type="tertiary", help="취소",
                          on_click=self._reset, key=self._key("cancel"))
            st.html(f"<style>.st-key-{cancel_key}{{align-items:flex-end}}</style>")
            st.progress(step / self.total, text=f"{step}/{self.total} 완료")
            st.markdown(f"#### {spec['description']}")

            if has_range:
                lo_txt = "−∞" if lo is None else lo
                hi_txt = "∞" if hi is None else hi
                st.caption(f"허용 범위: {lo_txt} ~ {hi_txt} {unit}".rstrip())

            # 대기 시간이 정의된 스텝에만 카운트다운 표시 (안내용 · 폼 밖)
            if spec.get("timer"):
                self._render_timer(step, spec["timer"])

            next_label = ":material/save: 저장" if is_last else "다음 :material/arrow_forward:"
            # 조회 전용(viewer)은 스텝은 둘러보되 마지막 '저장'만 막는다. DB 쓰기는 저장 확인
            # 다이얼로그에서만 일어나므로, 이 버튼을 비활성화하면 viewer 흐름엔 저장 경로가 없다.
            save_blocked = is_last and not can_edit
            nav_key, val_key = self._key("nav"), self._key("val")
            next_key, prev_key = self._key("submit_next"), self._key("submit_prev")
            # '다음/저장'과 '이전'을 모두 form_submit_button으로 폼 안에 둔다. 폼 위젯 값은
            # 폼 '제출' 시에만 session_state에 커밋되므로, '이전'을 폼 밖 일반 버튼으로 두면
            # 방금 입력한 값이 커밋되지 않아 유실된다(이전→다음 시 값이 사라지는 버그 — 실측 확인).
            # '다음'을 먼저 정의하면 submit이 2개여도 Enter는 항상 '다음'으로 간다(Enter=첫 submit,
            # 실측). 폼 enter_to_submit이 커서 위치와 무관하게 Enter를 잡아준다.
            # 폼 key에 step을 포함해 스텝 이동마다 폼을 remount → 제출 안 된 입력 버퍼가 폐기되어
            # 스텝 간 값 누수가 차단된다(고정 key 폼에선 버퍼가 잔류하다 다른 스텝 제출 때 누수됨).
            # 좌우 배치는 폼 래퍼를 display:contents로 평탄화해 입력칸·다음·이전을 flex 자식으로 만든 뒤 order로.
            with st.container(key=nav_key):
                with st.form(self._key(f"step_form_{step}"), border=False, clear_on_submit=False):
                    # key 고정("{p}_val")으로 스텝이 바뀌어도 위젯 재생성 없음(값은 콜백이 관리).
                    st.text_input(f"측정값 ({unit})" if unit else "측정값", key=val_key)
                    st.form_submit_button(next_label, type="primary", width="stretch",
                                          key=next_key, on_click=self._advance_step,
                                          disabled=save_blocked,
                                          help="조회 전용 계정은 저장할 수 없습니다." if save_blocked else None)
                    # '이전'도 폼 제출 버튼이라야 현재 입력값이 함께 커밋된다(첫 스텝엔 없음).
                    if step > 0:
                        st.form_submit_button(":material/arrow_back: 이전", width="stretch",
                                              key=prev_key, on_click=self._prev_step)
            # 폼/내부 블록을 display:contents로 평탄화 → 입력칸(1행 전체) / 이전·다음(2행 좌우).
            # flex-flow:row wrap을 명시(미지정 시 stVerticalBlock 기본 column을 물려받아 세로로 쌓임).
            st.html(f"""<style>
            .st-key-{nav_key} {{ display:flex; flex-flow:row wrap; gap:0.5rem; }}
            .st-key-{nav_key} > [data-testid="stLayoutWrapper"] {{ display:contents; }}
            .st-key-{nav_key} [data-testid="stForm"] {{ display:contents; padding:0; border:0; }}
            .st-key-{nav_key} [data-testid="stForm"] > [data-testid="stVerticalBlock"] {{ display:contents; }}
            .st-key-{val_key} {{ order:0; flex:0 0 100%; }}
            .st-key-{prev_key} {{ order:1; flex:1 1 0; min-width:0; }}
            .st-key-{next_key} {{ order:2; flex:1 1 0; min-width:0; }}
            </style>""")

    # ── 데이터 조회 (Raw Data) ────────────────────────────────
    def render_records(self) -> None:
        df = load_records()
        st.subheader("Raw Data")

        # 보드 접두사로 시작하고 검수 완료(verify_by NOT NULL)된 행만 표시한다.
        # (검수 중 데이터는 검수 리스트에서만 보이고, Raw Data엔 승인된 것만 노출)
        df = df[df["serial_number"].str.startswith(self.prefix) & df["verify_by"].notna()]

        if df.empty:
            st.info("검수 완료된 데이터가 없습니다.")
            return

        col1, col2 = st.columns(2)
        col1.metric("고유 Serial 수", df["serial_number"].nunique())
        col2.metric("고유 Test Item 수", df["test_item"].nunique())

        # Serial 필터: 미선택이면 전체 표시, 선택한 Serial들만 표시(다중 선택).
        options = df["serial_number"].unique().tolist()

        # 삭제 확인 다이얼로그. 내부 st.rerun()이 다이얼로그를 닫고 페이지를 재실행한다.
        @st.dialog("데이터 삭제 확인")
        def _confirm_delete(serials: list[str]) -> None:
            joined = ", ".join(f"**{s}**" for s in serials)
            st.markdown(f"{joined} 의 모든 데이터를 삭제합니다.")
            cancel_col, ok_col = st.columns(2)  # 취소 좌측 · 확인/삭제 우측
            if ok_col.button(":material/check: 확인", type="primary", width="stretch",
                             key=self._key("del_ok")):
                for s in serials:
                    delete_serial(s)
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
            # vertical_alignment="bottom"으로 multiselect와 버튼 하단을 맞춘다.
            sel_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
            selected = sel_col.multiselect("Serial 번호 선택", options,
                                           placeholder=PLACEHOLDER, key=self._key("filter_serial"))
            if btn_col.button(":material/delete: 삭제", type="primary", width="stretch",
                              disabled=not selected, key=self._key("del_btn")):
                _confirm_delete(selected)
        else:
            selected = st.multiselect("Serial 번호 선택", options,
                                      placeholder=PLACEHOLDER, key=self._key("filter_serial"))

        # 선택 Serial로 필터링해 조회 전용 테이블로 표시(미선택이면 전체).
        # test_datetime·verify_datetime은 원본(시각까지) 그대로 노출한다.
        view = df if not selected else df[df["serial_number"].isin(selected)]
        # test_By·verify_by에는 불변 oid가 저장돼 있으므로 화면에는 현재 이름으로 변환한다.
        # 매핑에 없는 값(레거시 행·미등록 oid)은 저장값 그대로 폴백한다.
        names = user_names()
        view = view.assign(
            test_By=view["test_By"].map(names).fillna(view["test_By"]),
            verify_by=view["verify_by"].map(names).fillna(view["verify_by"]),
        )

        # 선택(미선택 시 전체) Serial을 공식 양식(.xlsx)에 채워 다운로드. test_By가 이름으로
        # 변환된 view를 그대로 넘긴다. 양식이 없는 보드(Controller 등)는 버튼을 노출하지 않는다.
        if self.form:
            st.download_button(
                ":material/download: Download XLSX",
                data=build_filled_form(self.form["file"], self.form["sheet"],
                                       self.form["serial_col"], self.prefix, self.total, view),
                file_name=f"{self.form['file'].removesuffix('.xlsx')}_{datetime.now():%y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=view.empty, width="stretch", key=self._key("dl_form"),
            )

        st.dataframe(view, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
# steps가 채워진 보드만 위자드를 노출하고, 비어 있으면 "준비 중"으로 표시한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = BoardWizard(BOARD_CONFIG[label])
    with tab:
        st.subheader(label)
        if not wizard.total:
            st.info("준비 중입니다.")
        else:
            # 권한과 무관하게 위자드(TEST STEP)는 누구나 둘러볼 수 있다. 저장만 마지막 스텝에서
            # can_edit 여부로 막으므로(_render_step_wizard의 save_blocked), viewer도 진행은 가능하다.
            wizard.render_input()
            st.divider()
            wizard.render_records()
