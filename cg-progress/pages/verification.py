import pandas as pd
import streamlit as st

from constants import board_by_prefix, summary_records
from database import delete_pending, load_records, user_names, verify_serial

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

# verify_by가 NULL인 행이 '검수 중'이다(전체 공개 조회 후 파이썬에서 필터).
# 편집자는 test_By(불변 oid)가 본인 oid인 자신의 검수요청 건만 본다.
pending = load_records()
pending = pending[pending["verify_by"].isna()]
if is_editor:
    pending = pending[pending["test_By"] == st.user.oid]

# 직전 실행 결과를 토스트로 알린다(성공 ✅ / 경합 ⚠️).
# Streamlit은 세션 간 자동 푸시가 없어, 동시 접속 중 다른 사용자가 먼저 처리하면 내 화면은 stale가 된다.
# 그 경우 이미 사라진(처리된) 카드의 버튼 클릭은 rerun 과정에서 유실되어 핸들러(아래 승인/취소)가
# 실행되지 않으므로, 직전에 봤던 목록과 비교해 '외부 처리로 사라진 건'을 감지해 따로 알린다.
# (내가 직접 일으킨 액션 메시지 msg·warn이 있으면 그게 우선이다.)
current = set(pending["serial_number"])
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

if pending.empty:
    st.info("검수요청한 데이터가 없습니다." if is_editor else "검수 대기 중인 데이터가 없습니다.")
    st.stop()

st.markdown(f"#### {'검수요청' if is_editor else '검수 대기'} {pending['serial_number'].nunique()}건")

# Serial 단위로 한 번에 처리하므로 다이얼로그도 Serial 기준. (한 번에 하나만 열림)
# 관리자의 반려·편집자의 취소 모두 결국 해당 Serial 데이터를 삭제하므로 하나의 확인 다이얼로그를 공유한다.
@st.dialog("검수요청 취소" if is_editor else "데이터 삭제")
def _confirm_delete(serial: str) -> None:
    st.markdown((f"**{serial}** 의 검수요청을 취소하고 입력한 데이터를 삭제합니다."
                 if is_editor else f"**{serial}** 의 모든 데이터를 삭제합니다.") + " 되돌릴 수 없습니다.")
    back_col, ok_col = st.columns(2)  # 닫기 좌측 · 실행 우측
    ok_label = ":material/undo: 요청 취소" if is_editor else ":material/delete: 삭제"
    if ok_col.button(ok_label, type="primary", width="stretch", key="delete_ok"):
        # 검수 중인 건만 삭제한다. 동시 접속 중 관리자가 먼저 승인(또는 처리)했다면 대상이 없어
        # 0건이 반환되고 취소/반려는 무효화된다(stale 화면에서의 잘못된 삭제 방지).
        if delete_pending(serial, st.user.oid if is_editor else None):
            st.session_state["verify_msg"] = (f"**{serial}** 검수요청이 취소되었습니다." if is_editor
                                               else f"**{serial}** 반려(삭제)되었습니다.")
        else:
            st.session_state["verify_warn"] = f"**{serial}** 은(는) 이미 처리되어 취소할 수 없습니다."
        st.rerun()
    if back_col.button(":material/close: 닫기", width="stretch", key="delete_back"):
        st.rerun()

# 검수 카드 안의 표는 읽기 전용이라 dataframe 툴바를 숨긴다(한 번만 주입).
st.html('<style>[data-testid="stDataFrame"] [data-testid="stElementToolbar"]{display:none}</style>')

# test_By(oid)를 카드 캡션에 현재 이름으로 보여주기 위한 매핑. 없으면 저장값 그대로 폴백.
names = user_names()

# Serial별로 묶어 카드로 표시. load_records가 test_item 숫자순으로 정렬해 항목 순서가 보장된다.
for serial, group in pending.groupby("serial_number", sort=False):
    board = board_by_prefix(serial)
    steps = board["steps"] if board else []
    head = group.iloc[0]

    with st.container(border=True):
        st.markdown(f"#### {serial}")
        tester = names.get(head["test_By"], head["test_By"])
        st.caption(f"{head['test_datetime'][:10]}  ·  {tester}")

        # 데이터 확인 모달과 동일한 표(공용 summary_records). DB의 test_item(1-base)을
        # 스텝 인덱스(0-base)로 맞춰 측정값 dict를 만든 뒤 그대로 전달한다.
        values = {int(r["test_item"]) - 1: r["measurements"] for _, r in group.iterrows()}
        st.dataframe(pd.DataFrame(summary_records(steps, values)),
                     width="stretch", hide_index=True)

        # 편집자: 본인 요청을 거두는 '취소' 버튼 하나. 관리자: '반려'·'승인' 두 버튼.
        if is_editor:
            if st.button(":material/close: 취소", width="stretch", key=f"cancel_{serial}"):
                _confirm_delete(serial)
        else:
            reject_col, approve_col = st.columns(2)
            if reject_col.button(":material/close: 반려", width="stretch", key=f"reject_{serial}"):
                _confirm_delete(serial)
            if approve_col.button(":material/check: 승인", type="primary", width="stretch",
                                  key=f"approve_{serial}"):
                # 검수 중인 건만 승인된다. 편집자가 먼저 취소했다면 대상이 없어 무효화된다(경합 가드).
                if verify_serial(serial, st.user.oid):
                    st.session_state["verify_msg"] = f"**{serial}** 승인되었습니다."
                else:
                    st.session_state["verify_warn"] = f"**{serial}** 은(는) 이미 처리된 항목입니다."
                st.rerun()
