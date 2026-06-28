"""여러 페이지가 공유하는 UI 관용구 모음.

같은 패턴(oid→이름 변환·rerun 후 토스트·읽기전용 표 툴바 숨김·삭제 확인 모달)이 페이지마다
복붙돼 있어 한곳으로 모은다. 위젯 동작·문구는 기존과 동일하게 유지한다.
"""

import streamlit as st

from lib.database import user_names


def centered():
    """로그인·비활성 안내 등 전면(full-screen) 메시지를 가운데 좁은 폭에 배치하는 컬럼.
    layout="wide"에서 본문이 가로로 꽉 차므로, 양옆 여백 컬럼 사이의 가운데 컬럼을 반환한다.
    사용: ``with centered(): ...``"""
    return st.columns([1, 1.3, 1])[1]


def map_oids(view, *cols):
    """view의 지정 컬럼(test_By·test_by·verify_by 등 oid 저장)을 현재 이름으로 변환한 사본을 반환한다.
    매핑에 없는 값(레거시 행·미등록 oid)은 저장값 그대로 폴백한다."""
    names = user_names()
    return view.assign(**{c: view[c].map(names).fillna(view[c]) for c in cols})


def flash(key: str, icon: str):
    """직전 실행에서 남긴 메시지를 토스트로 띄운다(모달이 닫힌 뒤 rerun에서 표시). 없으면 무시."""
    msg = st.session_state.pop(key, None)
    if msg:
        st.toast(msg, icon=icon)


def hide_df_toolbar(scope: str = "page"):
    """읽기전용 dataframe의 툴바(검색·다운로드·열 표시/숨김)를 숨긴다.
    scope="dialog"는 모달 안 표만, "page"는 페이지 전체 표에 적용한다."""
    sel = '[role="dialog"]' if scope == "dialog" else '[data-testid="stDataFrame"]'
    st.html(f'<style>{sel} [data-testid="stElementToolbar"]{{display:none}}</style>')


def confirm_dialog(title: str, *, body: str, ok_label: str, on_confirm,
                   ok_type: str = "primary", cancel_label: str = ":material/close: 취소"):
    """확인/취소 2버튼 모달(취소 좌·확인 우). 확인 시 on_confirm()을 실행하고 닫는다.
    on_confirm은 DB 처리 + 결과 메시지를 session_state에 남기고, 닫힘(rerun)은 여기서 처리한다.
    모달은 한 번에 하나만 열리므로 위젯 key는 고정값으로 충분하다."""
    @st.dialog(title)
    def _dlg():
        st.markdown(body)
        cancel_col, ok_col = st.columns(2)
        if ok_col.button(ok_label, type=ok_type, width="stretch", key="confirm_ok"):
            on_confirm()
            st.rerun()
        if cancel_col.button(cancel_label, width="stretch", key="confirm_cancel"):
            st.rerun()

    _dlg()
