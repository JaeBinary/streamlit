import streamlit as st

st.title("Conformal Coating")
st.caption('CG PCBA 5종에 대한 "컨포멀 코팅" 두께를 측정합니다.')

# 탭 라벨 — 보드별 화면이 준비되면 info 자리에 내용을 채운다.
BOARD_LABELS = ["H-Bridge B/D", "Gate Driver B/D", "Bypass Capacitor B/D",
                "Tuning Capacitor B/D", "Controller B/D"]

for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    with tab:
        st.subheader(label)
        st.info("준비 중입니다.")
