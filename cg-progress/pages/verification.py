import pandas as pd
import streamlit as st

from constants import (COATING_POINTS, board_by_prefix, coating_summary_records,
                       summary_records)
from database import (delete_coating_pending, delete_pending, load_coating_records,
                      load_records, user_names, verify_coating_serial, verify_serial)
from ui import confirm_dialog, hide_df_toolbar

# 관리자·편집자 페이지. streamlit_app.py에서 해당 역할일 때만 네비게이션에 노출하지만,
# 페이지 단에서도 한 번 더 막아 URL 직접 접근 등 우회 진입을 차단한다(다층 방어).
# 관리자: 전체 검수 대기 건을 승인/반려한다. 편집자: 자신이 검수요청한 건만 보고 취소할 수 있다.
role = st.session_state.get("role", "viewer")

if role not in ("admin", "editor"):
    st.error("관리자·편집자만 접근할 수 있습니다.")
    st.stop()

is_editor = role == "editor"

st.title("Verification")
st.caption('내가 "검수요청한 데이터"를 확인하고 필요하면 요청을 취소합니다.' if is_editor
           else '저장된 "데이터를 검수"하여 승인하거나 반려(삭제)합니다.')


def _pending(load_fn, tester_col):
    """검수 중(verify_by IS NULL) 행만 추린다. 편집자는 본인 요청분(tester_col==oid)으로 제한한다.
    tester_col은 기능 테스트=test_By, 코팅=test_by로 테이블마다 다르다."""
    df = load_fn()
    df = df[df["verify_by"].isna()]
    if is_editor:
        df = df[df[tester_col] == st.user.oid]
    return df


def _functional_summary(serial, group):
    """기능 테스트 그룹 → 요약 표. test_item(1-base)을 스텝 인덱스(0-base)로 맞춘다."""
    board = board_by_prefix(serial)
    steps = board["steps"] if board else []
    values = {int(r["test_item"]) - 1: r["measurements"] for _, r in group.iterrows()}
    return summary_records(steps, values)


def _coating_summary(serial, group):
    """코팅 그룹 → 요약 표. coating_point(TOP-1 등)를 포인트 인덱스(0-base)로 맞춘다."""
    values = {COATING_POINTS.index(r["coating_point"]): r["measurements"]
              for _, r in group.iterrows() if r["coating_point"] in COATING_POINTS}
    return coating_summary_records(values)


# 검수 대상은 기능 테스트·코팅 두 종류. 표/검증 함수만 다르고 카드 흐름은 공유한다(아래 render_cards).
SOURCES = [
    {"kind": "func", "title": "Functional Test", "tester_col": "test_By",
     "pending": _pending(load_records, "test_By"),
     "summary": _functional_summary, "verify": verify_serial, "delete": delete_pending},
    {"kind": "coat", "title": "Conformal Coating", "tester_col": "test_by",
     "pending": _pending(load_coating_records, "test_by"),
     "summary": _coating_summary, "verify": verify_coating_serial, "delete": delete_coating_pending},
]

# 직전 실행 결과를 토스트로 알린다(성공 ✅ / 경합 ⚠️).
# 동시 접속 중 다른 사용자가 먼저 처리하면 내 화면은 stale가 되고, 이미 사라진 카드의 버튼 클릭은
# rerun에서 유실되어 핸들러가 안 돈다. 그래서 직전에 봤던 목록과 비교해 '외부 처리로 사라진 건'을
# 따로 감지해 알린다. 종류가 둘이라 (kind, serial)로 묶어 같은 Serial이 양쪽에 있어도 구분한다.
current = {(s["kind"], serial) for s in SOURCES for serial in s["pending"]["serial_number"]}
vanished = st.session_state.get("verify_seen", set()) - current
st.session_state["verify_seen"] = current

msg = st.session_state.pop("verify_msg", None)
warn = st.session_state.pop("verify_warn", None)
if msg:
    st.toast(msg, icon="✅")
elif warn:
    st.toast(warn, icon="⚠️")
elif vanished:
    st.toast("이미 처리되었습니다.", icon="⚠️")

# 검수 카드 안의 표는 읽기 전용이라 dataframe 툴바를 숨긴다(한 번만 주입).
hide_df_toolbar("page")

# test_by(oid)를 카드 캡션에 현재 이름으로 보여주기 위한 매핑. 없으면 저장값 그대로 폴백.
names = user_names()


# Serial 단위로 한 번에 처리하므로 다이얼로그도 Serial 기준. (한 번에 하나만 열림)
# 관리자의 반려·편집자의 취소 모두 결국 해당 Serial 데이터를 삭제하므로 하나의 확인 다이얼로그를 공유한다.
# 삭제 함수만 종류별로 받아 처리한다(delete_pending / delete_coating_pending — 시그니처 동일).
def _confirm_delete(serial: str, delete_fn) -> None:
    def _on_confirm() -> None:
        # 검수 중인 건만 삭제한다. 동시 접속 중 관리자가 먼저 승인(또는 처리)했다면 대상이 없어
        # 0건이 반환되고 취소/반려는 무효화된다(stale 화면에서의 잘못된 삭제 방지).
        if delete_fn(serial, st.user.oid if is_editor else None):
            st.session_state["verify_msg"] = (f"**{serial}** 검수요청이 취소되었습니다." if is_editor
                                               else f"**{serial}** 반려(삭제)되었습니다.")
        else:
            st.session_state["verify_warn"] = f"**{serial}** 은(는) 이미 처리되어 취소할 수 없습니다."

    confirm_dialog(
        "검수요청 취소" if is_editor else "데이터 삭제",
        body=(f"**{serial}** 의 검수요청을 취소하고 입력한 데이터를 삭제합니다."
              if is_editor else f"**{serial}** 의 모든 데이터를 삭제합니다.") + " 되돌릴 수 없습니다.",
        ok_label=":material/undo: 요청 취소" if is_editor else ":material/delete: 삭제",
        on_confirm=_on_confirm, cancel_label=":material/close: 닫기",
    )


def render_cards(src: dict) -> None:
    """한 종류(기능/코팅)의 검수 대기 카드를 Serial별로 렌더한다(해당 탭 안에서 호출).
    위젯 key는 kind로 네임스페이스해 같은 Serial이 양쪽에 있어도 충돌하지 않는다."""
    pending, kind = src["pending"], src["kind"]
    if pending.empty:
        st.info("검수요청한 데이터가 없습니다." if is_editor else "검수 대기 중인 데이터가 없습니다.")
        return

    # 탭 라벨이 이미 종류(기능/코팅)를 나타내므로 헤더엔 건수만 표시한다.
    st.markdown(f"#### {'검수요청' if is_editor else '검수 대기'} {pending['serial_number'].nunique()}건")
    for serial, group in pending.groupby("serial_number", sort=False):
        head = group.iloc[0]
        with st.container(border=True):
            st.markdown(f"#### {serial}")
            tester = names.get(head[src["tester_col"]], head[src["tester_col"]])
            st.caption(f"{head['test_datetime'][:10]}  ·  {tester}")
            st.dataframe(pd.DataFrame(src["summary"](serial, group)),
                         width="stretch", hide_index=True)

            # 편집자: 본인 요청을 거두는 '취소' 버튼 하나. 관리자: '반려'·'승인' 두 버튼.
            if is_editor:
                if st.button(":material/close: 취소", width="stretch", key=f"{kind}_cancel_{serial}"):
                    _confirm_delete(serial, src["delete"])
            else:
                reject_col, approve_col = st.columns(2)
                if reject_col.button(":material/close: 반려", width="stretch", key=f"{kind}_reject_{serial}"):
                    _confirm_delete(serial, src["delete"])
                if approve_col.button(":material/check: 승인", type="primary", width="stretch",
                                      key=f"{kind}_approve_{serial}"):
                    # 검수 중인 건만 승인된다. 편집자가 먼저 취소했다면 대상이 없어 무효화된다(경합 가드).
                    if src["verify"](serial, st.user.oid):
                        st.session_state["verify_msg"] = f"**{serial}** 승인되었습니다."
                    else:
                        st.session_state["verify_warn"] = f"**{serial}** 은(는) 이미 처리된 항목입니다."
                    st.rerun()


# 종류별 탭으로 구분. 탭 라벨은 SOURCES 순서(기능 테스트 → 코팅)와 1:1 대응한다.
for tab, src in zip(st.tabs([s["title"] for s in SOURCES]), SOURCES):
    with tab:
        render_cards(src)
