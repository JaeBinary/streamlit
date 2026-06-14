import streamlit as st

role = st.session_state.get("role", "viewer")

st.title("Conformal Coating")
st.caption('CG PCBA 5종에 대한 "컨포멀 코팅" 두께를 측정합니다.')

TABS = ["H-Bridge B/D", "Gate Driver B/D", "Bypass Capacitor B/D", "Tuning Capacitor B/D", "Controller B/D"]
tab_hBridge, tab_gateDriver, tab_bypassCapacitor, tab_tuningCapacitor, tab_controller = st.tabs(TABS)

with tab_hBridge:
    st.subheader("H-Bridge Board")
    st.info("준비 중입니다.")

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
