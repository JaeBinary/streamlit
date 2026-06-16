import streamlit as st

from constants import BOARD_CONFIG, BOARD_LABELS
from database import insert_records, load_records

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
      {p}_done   : 전체 스텝 저장 완료 플래그
    위젯 key도 모두 prefix로 분리해 여러 보드가 동시에 렌더돼도 충돌하지 않는다.
    """

    def __init__(self, label: str, cfg: dict) -> None:
        self.label = label
        self.prefix = cfg["prefix"]
        self.digits = cfg["digits"]
        self.steps = cfg["steps"]
        self.total = len(self.steps)
        # Serial 입력 예시 (placeholder·에러 문구 공용): 예) H0021
        self.example = f"{self.prefix}{21:0{self.digits}d}"

    # ── 세션 키 (prefix 네임스페이스) ─────────────────────────
    def _key(self, name: str) -> str:
        return f"{self.prefix}_{name}"

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
        step = st.session_state[self._key("step")]
        values = st.session_state[self._key("values")]
        values[step] = st.session_state[self._key("val")]
        if step >= self.total - 1:
            base = st.session_state[self._key("base")]
            rows = [
                (base["serial"], i + 1, base["test_date"], base["tested_by"], values[i])
                for i in range(self.total)
            ]
            insert_records(rows, st.user.email)
            st.session_state[self._key("done")] = True
        else:
            st.session_state[self._key("step")] += 1
            # 다음 스텝의 저장값(없으면 빈값)으로 입력칸을 갈아끼운다. key가 고정이라
            # 위젯 재생성 없이 값만 바뀌므로 폼이 안정적으로 유지된다.
            st.session_state[self._key("val")] = values.get(st.session_state[self._key("step")], "")

    def _prev_step(self) -> None:
        if st.session_state[self._key("step")] > 0:
            st.session_state[self._key("values")][st.session_state[self._key("step")]] = st.session_state[self._key("val")]
            st.session_state[self._key("step")] -= 1
            st.session_state[self._key("val")] = st.session_state[self._key("values")].get(st.session_state[self._key("step")], "")

    def _reset(self) -> None:
        for name in ("base", "step", "values", "val", "done"):
            st.session_state.pop(self._key(name), None)

    # ── 입력 폼 ───────────────────────────────────────────────
    def render_input(self) -> None:
        """① 기본 정보(Serial·날짜·담당자) 확인 → ② 스텝 측정값 입력 → 일괄 저장."""
        if self._key("base") not in st.session_state:
            self._render_base_form()
        else:
            self._render_step_wizard()

    def _render_base_form(self) -> None:
        # 폼 대신 컨테이너 + 일반 버튼 사용. 이 화면은 Enter 제출이 필요 없고,
        # 폼이면 페이지 첫 렌더 때 submit 버튼이 한 프레임 늦게 도착해
        # "Missing Submit Button"이 깜빡이기 때문이다. (측정값 스텝만 폼 유지)
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            serial = col1.text_input("Serial 번호", placeholder=f"예시: 21 or {self.example}",
                                     key=self._key("in_serial"))
            test_date = col2.date_input("테스트 날짜", key=self._key("in_date"))
            tested_by = col3.text_input("테스트 담당자", value=st.user.name, key=self._key("in_by"))
            confirmed = st.button("확인", type="primary", width="stretch", key=self._key("confirm"))

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

        st.session_state[self._key("base")] = {
            "serial": serial_norm,
            "test_date": test_date.isoformat(),
            "tested_by": tested_by.strip(),
        }
        st.session_state[self._key("step")] = 0
        st.session_state[self._key("values")] = {}
        st.session_state[self._key("val")] = ""
        st.rerun()

    def _render_step_wizard(self) -> None:
        base = st.session_state[self._key("base")]

        # 저장 완료 화면
        if st.session_state.get(self._key("done")):
            st.success(f"✅ **{base['serial']}** / {self.total}개 스텝이 저장되었습니다!")
            st.button("➕ 새 항목 추가", type="primary", on_click=self._reset, key=self._key("new"))
            return

        step = st.session_state[self._key("step")]
        spec = self.steps[step]
        lo, hi, unit = spec["min"], spec["max"], spec["unit"]
        has_range = lo is not None or hi is not None
        is_last = step == self.total - 1

        # 기본 정보 폼과 동일한 테두리 박스 안에 스텝 입력을 배치한다.
        with st.container(border=True):
            st.caption(f"**{base['serial']}**  ·  {base['test_date']}  ·  {base['tested_by']}")
            st.progress(step / self.total, text=f"{step}/{self.total} 완료")
            st.markdown(f"#### {spec['description']}")

            if has_range:
                lo_txt = "−∞" if lo is None else lo
                hi_txt = "∞" if hi is None else hi
                st.caption(f"허용 범위: {lo_txt} ~ {hi_txt} {unit}".rstrip())

            # 입력칸 + '다음'을 폼으로 묶으면 측정값에서 Enter만 눌러도 다음 스텝으로 넘어간다.
            # (폼에 submit 버튼이 하나면 Enter == 그 버튼 클릭)
            with st.form(self._key("step_form"), border=False, clear_on_submit=False):
                # key를 고정("{p}_val")해 스텝이 바뀌어도 위젯이 재생성되지 않게 한다.
                # (값은 _advance_step/_prev_step 콜백에서 세션 상태로 관리)
                st.text_input(f"측정값 ({unit})" if unit else "측정값", key=self._key("val"))
                st.form_submit_button(
                    "저장 완료" if is_last else "다음 →", type="primary",
                    width="stretch", on_click=self._advance_step,
                )

            # 이전 / 취소 — 폼 밖 일반 버튼 (Enter 제출 대상이 아님)
            col_prev, col_cancel = st.columns(2)
            with col_prev:
                if step > 0:
                    st.button("← 이전", width="stretch", on_click=self._prev_step, key=self._key("prev"))
            with col_cancel:
                st.button("취소", width="stretch", on_click=self._reset, key=self._key("cancel"))

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

        # 조회 전용 — 수정·삭제는 지원하지 않으므로 st.dataframe으로 표시한다.
        # (헤더는 DB에 저장된 컬럼명 그대로 노출)
        st.dataframe(df, width="stretch", hide_index=True)


# ── 탭 구성 ───────────────────────────────────────────────
# STEPS가 채워진 보드만 위자드를 노출하고, 비어 있으면 "준비 중"으로 표시한다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    wizard = BoardWizard(label, BOARD_CONFIG[label])
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
