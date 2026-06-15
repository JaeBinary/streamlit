import streamlit as st

from database import insert_records, load_records

# 위자드 각 스텝 정의 — 순서대로 1~25번 스텝.
#   description : 화면에 표시할 문구 (번호는 문구에 직접 포함)
#   min / max: 허용 범위. None이면 범위 표시·경고 없음. 범위 밖 값도 저장은 가능.
#   unit     : 측정 단위 (없으면 "")
# min/max/unit은 화면 표시·경고용일 뿐 DB에는 저장되지 않는다.
# (DB의 test_item에는 스텝 번호 1~25, measurements에는 측정값만 저장된다.)
STEPS = [
    {"description": "01. Measure the resistance across the component R11", "min": 9.9, "max": 10.1, "unit": "Ω"},
    {"description": "02. Measure the resistance across the component R12", "min": 9.9, "max": 10.1, "unit": "Ω"},
    {"description": "03. Measure the resistance across the component R13", "min": 9.9, "max": 10.1, "unit": "Ω"},
    {"description": "04. Measure the resistance across the component R3", "min": 9.9, "max": 10.1, "unit": "Ω"},
    {"description": "05. Measure the capacitance across the component C1", "min": 4.5e-08, "max": 4.9e-08, "unit": "F"},
    {"description": "06. Measure the capacitance across the component C2", "min": 4.5e-08, "max": 4.9e-08, "unit": "F"},
    {"description": "07. Measure the capacitance across the component C3", "min": 4.5e-08, "max": 4.9e-08, "unit": "F"},
    {"description": "08. Measure the capacitance across the component C4", "min": 4.5e-08, "max": 4.9e-08, "unit": "F"},
    {"description": "09. Check the continuity on these points J8 and J9", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "10. Check the continuity on these points J14-1 and J14-2", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "11. Check the continuity on these points J14-3 and J14-4", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "12. Check the continuity on these points J14-5 and J14-6", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "13. Check the continuity on these points J14-7 and J14-8", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "14. Check the continuity on these points J14-9 and J14-10", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "15. Check the continuity on these points J14-11 and J14-12", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "16. Check the continuity on these points J14-13 and J14-14", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "17. Check the continuity on these points J14-15 and J14-16", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "18. Check the continuity on these points J14-17 and J14-18", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "19. Check the continuity on these points J14-19 and J14-20", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "20. Check the continuity on these points J14-21 and J14-22", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "21. Check the continuity on these points J14-23 and J14-24", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "22. Check the continuity on these points J14-25 and J14-26", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "23. Check the continuity on these points J14-27 and J14-28", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "24. Check the continuity on these points J14-29 and J14-30", "min": 350, "max": 450, "unit": "Ω"},
    {"description": "25. Checking the continuity of J14-1 and J14-2 After R1 and R2 were screwed on their designated footprint", "min": 350, "max": 450, "unit": "Ω"},
]
TOTAL_STEPS = len(STEPS)

role = st.session_state.get("role", "viewer")
can_edit = role in ("admin", "editor")

st.title("Functional Test")
st.caption('CG PCBA 5종에 대한 "기능 테스트"를 진행합니다.')


# ── 입력 폼 ───────────────────────────────────────────────
# 위자드 진행 상태는 ht_* 세션 키에 보관한다.
#   ht_base   : {"serial", "test_date", "tested_by"}  (기본 정보 확인 시 생성 → 위자드 진입)
#   ht_step   : 현재 스텝 인덱스 (0 ~ TOTAL_STEPS)
#   ht_values : {스텝 인덱스: 측정값}
#   ht_val    : 현재 측정값 입력칸의 값(위젯 key). 스텝마다 콜백에서 갈아끼운다.
#   ht_done   : 25스텝 저장 완료 플래그
_WIZARD_KEYS = ("ht_base", "ht_step", "ht_values", "ht_val", "ht_done")


def render_input_form() -> None:
    """① 기본 정보(Serial·날짜·담당자) 확인 → ② 25스텝 측정값 입력 → 일괄 저장."""
    if "ht_base" not in st.session_state:
        _render_base_form()
    else:
        _render_step_wizard()


def _normalize_serial(raw: str) -> str | None:
    """H-Bridge Serial을 'H' + 숫자 4자리로 정규화. '21'·'H21'·'0021' → 'H0021'. 형식 오류 시 None."""
    s = raw.strip().upper().removeprefix("H")
    if not s.isdigit() or len(s) > 4:
        return None
    return f"H{int(s):04d}"


def _render_base_form() -> None:
    # 폼 대신 컨테이너 + 일반 버튼 사용. 이 화면은 Enter 제출이 필요 없고,
    # 폼이면 페이지 첫 렌더 때 submit 버튼이 한 프레임 늦게 도착해
    # "Missing Submit Button"이 깜빡이기 때문이다. (측정값 스텝만 폼 유지)
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        serial = col1.text_input("Serial 번호", placeholder="예시: 21 or H0021")
        test_date = col2.date_input("테스트 날짜")
        tested_by = col3.text_input("테스트 담당자", value=st.user.name)
        confirmed = st.button("확인", type="primary", width="stretch")

    if not confirmed:
        return

    serial_norm = _normalize_serial(serial)
    if serial_norm is None:
        st.error("Serial 번호는 'H + 숫자 4자리' 형식입니다. 숫자만 입력해도 됩니다 (예: 21 → H0021).")
        return
    if not tested_by.strip():
        st.error("테스트 담당자는 필수 항목입니다.")
        return

    st.session_state.ht_base = {
        "serial": serial_norm,
        "test_date": test_date.isoformat(),
        "tested_by": tested_by.strip(),
    }
    st.session_state.ht_step = 0
    st.session_state.ht_values = {}
    st.session_state.ht_val = ""
    st.rerun()


def _reset_wizard() -> None:
    for key in _WIZARD_KEYS:
        st.session_state.pop(key, None)


# ── 위자드 콜백 ───────────────────────────────────────────
# 버튼 처리는 st.rerun() 대신 on_click 콜백으로 한다. 콜백은 스크립트 재실행 '전'에
# 실행되어 rerun이 한 번만 깔끔히 돌기 때문에, 폼 제출 직후 이중 rerun으로 폼이
# 허물어지며 "Missing Submit Button"이 깜빡이는 현상이 사라진다.
def _advance_step() -> None:
    """현재 스텝 값을 저장하고 다음 스텝으로(마지막이면 25건 일괄 저장)."""
    step = st.session_state.ht_step
    values = st.session_state.ht_values
    values[step] = st.session_state.ht_val
    if step >= TOTAL_STEPS - 1:
        base = st.session_state.ht_base
        rows = [
            (base["serial"], i + 1, base["test_date"], base["tested_by"], values[i])
            for i in range(TOTAL_STEPS)
        ]
        insert_records(rows, st.user.email)
        st.session_state.ht_done = True
    else:
        st.session_state.ht_step += 1
        # 다음 스텝의 저장값(없으면 빈값)으로 입력칸을 갈아끼운다. key가 고정이라
        # 위젯 재생성 없이 값만 바뀌므로 폼이 안정적으로 유지된다.
        st.session_state.ht_val = values.get(st.session_state.ht_step, "")


def _prev_step() -> None:
    if st.session_state.ht_step > 0:
        st.session_state.ht_values[st.session_state.ht_step] = st.session_state.ht_val
        st.session_state.ht_step -= 1
        st.session_state.ht_val = st.session_state.ht_values.get(st.session_state.ht_step, "")


def _render_step_wizard() -> None:
    base = st.session_state.ht_base

    # 저장 완료 화면
    if st.session_state.get("ht_done"):
        st.success(f"✅ **{base['serial']}** / {TOTAL_STEPS}개 스텝이 저장되었습니다!")
        st.button("➕ 새 항목 추가", type="primary", on_click=_reset_wizard)
        return

    step = st.session_state.ht_step
    spec = STEPS[step]
    lo, hi, unit = spec["min"], spec["max"], spec["unit"]
    has_range = lo is not None or hi is not None
    is_last = step == TOTAL_STEPS - 1

    # 기본 정보 폼과 동일한 테두리 박스 안에 스텝 입력을 배치한다.
    with st.container(border=True):
        st.caption(f"**{base['serial']}**  ·  {base['test_date']}  ·  {base['tested_by']}")
        st.progress(step / TOTAL_STEPS, text=f"{step}/{TOTAL_STEPS} 완료")
        st.markdown(f"#### {spec['description']}")

        if has_range:
            lo_txt = "−∞" if lo is None else lo
            hi_txt = "∞" if hi is None else hi
            st.caption(f"허용 범위: {lo_txt} ~ {hi_txt} {unit}".rstrip())

        # 입력칸 + '다음'을 폼으로 묶으면 측정값에서 Enter만 눌러도 다음 스텝으로 넘어간다.
        # (폼에 submit 버튼이 하나면 Enter == 그 버튼 클릭)
        with st.form("ht_step_form", border=False, clear_on_submit=False):
            # key를 고정("ht_val")해 스텝이 바뀌어도 위젯이 재생성되지 않게 한다.
            # (값은 _advance_step/_prev_step 콜백에서 st.session_state.ht_val로 관리)
            st.text_input(f"측정값 ({unit})" if unit else "측정값", key="ht_val")
            st.form_submit_button(
                "저장 완료" if is_last else "다음 →", type="primary",
                width="stretch", on_click=_advance_step,
            )

        # 이전 / 취소 — 폼 밖 일반 버튼 (Enter 제출 대상이 아님)
        col_prev, col_cancel = st.columns(2)
        with col_prev:
            if step > 0:
                st.button("← 이전", width="stretch", on_click=_prev_step)
        with col_cancel:
            st.button("취소", width="stretch", on_click=_reset_wizard)


# ── 데이터 조회 (Raw Data) ────────────────────────────────
def render_records() -> None:
    df = load_records(st.user.email, role)
    st.subheader(f"Raw Data")

    if df.empty:
        st.info("아직 저장된 데이터가 없습니다.")
        return

    col1, col2 = st.columns(2)
    col1.metric("고유 Serial 수", df["serial"].nunique())
    col2.metric("고유 Test Item 수", df["test_item"].nunique())

    # 조회 전용 — 수정·삭제는 지원하지 않으므로 st.dataframe으로 표시한다.
    # (헤더는 DB에 저장된 컬럼명 그대로 노출)
    st.dataframe(df, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
TAB_LABELS = ["H-Bridge B/D", "Gate Driver B/D", "Bypass Capacitor B/D",
              "Tuning Capacitor B/D", "Controller B/D"]
tab_hbridge, *other_tabs = st.tabs(TAB_LABELS)

with tab_hbridge:
    st.subheader(TAB_LABELS[0])
    if can_edit:
        render_input_form()
    else:
        st.info("조회 전용 계정입니다. 데이터를 추가하려면 관리자에게 권한을 요청하세요.")
    st.divider()
    render_records()

for tab, label in zip(other_tabs, TAB_LABELS[1:]):
    with tab:
        st.subheader(label)
        st.info("준비 중입니다.")
