from datetime import datetime

import streamlit as st

from database import bulk_update_records, clear_records, delete_record, insert_record, load_records

role = st.session_state.get("role", "viewer")

st.title("Functional Test")
st.caption('CG PCBA 5종에 대한 "기능 테스트"를 진행합니다.')

TABS = ["H-Bridge B/D", "Gate Driver B/D", "Bypass Capacitor B/D", "Tuning Capacitor B/D", "Controller B/D"]
tab_hBridge, tab_gateDriver, tab_bypassCapacitor, tab_tuningCapacitor, tab_controller = st.tabs(TABS)

with tab_hBridge:
    st.subheader("H-Bridge Board")
    # ── 입력 폼 ───────────────────────────────────────────────
    if role == "viewer":
        st.info("조회 전용 계정입니다. 데이터를 추가하려면 관리자에게 권한을 요청하세요.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            serial = st.text_input("Serial 번호", key="q_serial")
        with col2:
            test_date = st.date_input("테스트 날짜", key="q_test_date")
        with col3:
            if "q_test_by" not in st.session_state:
                st.session_state["q_test_by"] = st.user.name
            test_by = st.text_input("테스트 담당자", key="q_test_by")

        all_filled = bool(serial.strip() and test_by.strip())
        if st.button("확인", type="primary", disabled=not all_filled, use_container_width=True):
            st.session_state.show_steps = True
            st.session_state.q_step = 0
            st.session_state.q_answers = {}

        # Q4~Q5: 스텝 위자드 (기본 정보 입력 후 표시)
        if st.session_state.get("show_steps", False):
            STEPS = [
                [{"key": "test_item",    "label": "Q1. Test Item을 입력하세요.",     "type": "text"}],
                [{"key": "measurements", "label": "Q2. Measurements를 입력하세요.", "type": "textarea"}],
            ]
            ALL_QUESTIONS = [q for step_qs in STEPS for q in step_qs]

            if "q_step" not in st.session_state:
                st.session_state.q_step = 0
                st.session_state.q_answers = {}

            step = st.session_state.q_step
            total = len(STEPS)

            if step < total:
                step_qs = STEPS[step]
                st.progress(step / total, text=f"{step}/{total} 완료")

                vals = {}
                for q in step_qs:
                    st.markdown(f"**{q['label']}**")
                    saved = st.session_state.q_answers.get(q["key"])
                    if q["type"] == "text":
                        vals[q["key"]] = st.text_input("답변", label_visibility="collapsed",
                                            value=saved or "", key=f"q_{q['key']}")
                    elif q["type"] == "textarea":
                        vals[q["key"]] = st.text_area("답변", placeholder="측정값을 입력하세요...",
                                        value=saved or "",
                                        label_visibility="collapsed", key=f"q_{q['key']}")

                col_prev, col_next = st.columns([1, 3])
                with col_prev:
                    if step > 0 and st.button("← 이전", use_container_width=True):
                        st.session_state.q_answers.update(vals)
                        st.session_state.q_step -= 1
                        st.rerun()
                with col_next:
                    btn_label = "다음 →" if step < total - 1 else "저장 완료"
                    if st.button(btn_label, type="primary", use_container_width=True):
                        invalid = [q for q in step_qs if q["type"] == "text" and not vals[q["key"]].strip()]
                        if invalid:
                            st.error("값을 입력해주세요.")
                        else:
                            st.session_state.q_answers.update(vals)
                            st.session_state.q_step += 1
                            st.rerun()
            else:
                a = st.session_state.q_answers
                insert_record(serial, test_date.isoformat(), test_by, a["test_item"], a["measurements"], st.user.email)
                st.success(f"✅ Serial **{serial}** / {a['test_item']} 결과가 저장되었습니다!")

                st.markdown("**입력 내용 요약**")
                st.write(f"- Serial 번호 **{serial}**")
                st.write(f"- 테스트 날짜 **{test_date.isoformat()}**")
                st.write(f"- 테스트 담당자 **{test_by}**")
                for q in ALL_QUESTIONS:
                    st.write(f"- {q['label'].split('. ')[1]} **{a[q['key']]}**")

                if st.button("➕ 새 항목 추가", type="primary"):
                    st.session_state.q_step = 0
                    st.session_state.q_answers = {}
                    st.session_state.show_steps = False
                    st.session_state["q_serial"] = ""
                    st.session_state["q_test_by"] = st.user.name
                    st.rerun()

    # ── 데이터 조회 ───────────────────────────────────────────
    st.divider()
    df = load_records(st.user.email, role)
    label = "전체 데이터" if role == "admin" else "내 데이터"
    st.subheader(f"{label} ({len(df)}건)")

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("총 항목 수", len(df))
        col2.metric("고유 Serial 수", df["serial"].nunique())
        col3.metric("고유 Test Item 수", df["test_item"].nunique())

        DISPLAY_COLS = [c for c in df.columns if c != "id"]
        is_editable = role in ("admin", "editor")
        st.caption("셀을 클릭해서 수정한 뒤 💾 변경사항 저장을 누르세요." if is_editable else "")
        st.data_editor(
            df[DISPLAY_COLS],
            use_container_width=True,
            num_rows="fixed",
            disabled=not is_editable,
            column_config={
                "serial":       st.column_config.TextColumn("Serial"),
                "test_date":    st.column_config.TextColumn("Test Date"),
                "test_by":      st.column_config.TextColumn("Test By"),
                "test_item":    st.column_config.TextColumn("Test Item"),
                "measurements": st.column_config.TextColumn("Measurements"),
                "saved_by":     st.column_config.TextColumn("Saved By",   disabled=True),
                "created_at":   st.column_config.TextColumn("Created At", disabled=True),
            },
            hide_index=False,
            key="data_editor",
        )

        if is_editable:
            col_save, col_del = st.columns([3, 1])
            with col_save:
                if st.button("💾 변경사항 저장", type="primary", use_container_width=True):
                    edited_rows = st.session_state.get("data_editor", {}).get("edited_rows", {})
                    if not edited_rows:
                        st.info("수정된 내용이 없습니다.")
                    else:
                        updates = []
                        for row_idx, changes in edited_rows.items():
                            row_id = int(df.loc[row_idx, "id"])
                            current = df.loc[row_idx]
                            updates.append((
                                row_id,
                                changes.get("serial",       current["serial"]),
                                changes.get("test_date",    current["test_date"]),
                                changes.get("test_by",      current["test_by"]),
                                changes.get("test_item",    current["test_item"]),
                                changes.get("measurements", current["measurements"]),
                            ))
                        bulk_update_records(updates)
                        st.success(f"{len(updates)}개 행이 수정되었습니다.")
                        st.rerun()
            with col_del:
                with st.popover("🗑️ 행 삭제", use_container_width=True):
                    del_idx = st.number_input("삭제할 행 번호", min_value=0,
                                            max_value=len(df) - 1, step=1)
                    if st.button("삭제 확인", type="secondary"):
                        delete_record(int(df.loc[del_idx, "id"]))
                        st.rerun()

        csv = df[DISPLAY_COLS].to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 CSV로 다운로드",
            data=csv,
            file_name=f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if is_editable and st.button("🗑️ 전체 초기화", type="secondary"):
            clear_records(st.user.email, role)
            st.rerun()
    else:
        st.info("아직 저장된 데이터가 없습니다.")

with tab_gateDriver:
    st.subheader("Gate Driver Board")
    st.info("준비 중입니다.")
with tab_bypassCapacitor:
    st.subheader("Bypass Capacitor Board")
    st.info("준비 중입니다.")
with tab_tuningCapacitor:
    st.subheader("Tuning Capacitor Board")
    st.info("준비 중입니다.")
with tab_controller:
    st.subheader("Controller Board")
    st.info("준비 중입니다.")
