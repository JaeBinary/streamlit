import streamlit as st

from constants import BOARD_LABELS

st.title("Conformal Coating")
st.caption('CG PCBA 5종에 대한 "컨포멀 코팅" 두께를 측정합니다.')

# 보드별 화면이 준비되면 info 자리에 내용을 채운다.
for tab, label in zip(st.tabs(BOARD_LABELS), BOARD_LABELS):
    with tab:
        st.subheader(label)
        st.info("준비 중입니다.")
