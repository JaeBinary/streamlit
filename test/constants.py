"""여러 페이지가 공유하는 상수 모음.

라벨이 여러 파일에 흩어져 복사되면 추가/이름 변경 시 누락이 생기므로 한곳에 모은다.
"""

# CG PCBA 5종 보드 설정. 보드마다 다른 값을 한 곳에서 관리한다.
#   prefix : Serial 접두사. 보드 구분 기준 — Serial 정규화·조회 필터에 사용.
#   digits : Serial 숫자 자리수 (예: digits=4 → H0021).
#   steps  : 기능 테스트 위자드의 측정 스텝 정의.
#     description : 화면에 표시할 문구 (번호는 문구에 직접 포함)
#     min / max   : 허용 범위. None이면 범위 표시·경고 없음. 범위 밖 값도 저장은 가능.
#     unit        : 측정 단위 (없으면 "")
#   min/max/unit은 화면 표시·경고용일 뿐 DB에는 저장되지 않는다.
#   (DB의 test_item에는 스텝 번호, measurements에는 측정값만 저장된다.)
BOARD_CONFIG = {
    "H-Bridge B/D": {
        "prefix": "H",
        "digits": 4,
        "steps": [
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
        ],
    },
    # 아래 4종은 Serial 규칙만 확정. STEPS는 추후 채운다(비어 있으면 화면에 "준비 중"으로 표시).
    "Gate Driver B/D": {
        "prefix": "G",
        "digits": 4,
        "steps": [
            {"description": "01. Pin4 (Anode) and Pin 1 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "02. Pin2 (Anode) and Pin 1 (Cathode)", "min": 0.85, "max": 1.1, "unit": "V"},
            {"description": "03. Pin3 (Anode) and Pin 1 (Cathode)", "min": 0.85, "max": 1.1, "unit": "V"},
            {"description": "04. Pin10 (Anode) and Pin 11 (Cathode)", "min": 0.5, "max": 0.8, "unit": "V"},
            {"description": "05. Pin11 (Anode) and Pin 12 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "06. Pin6 (Anode) and Pin 7 (Cathode)", "min": 0.5, "max": 0.8, "unit": "V"},
            {"description": "07. Pin7 (Anode) and Pin 1 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "08. Pin1 (Anode) and Pin 12 (Cathode)", "min": 0.75, "max": 1.2, "unit": "V"},
            {"description": "09. Pin5 (Anode) and Pin 2 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "10. Pin5 (Anode) and Pin 3 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "11. Pin2 (Anode) and Pin 1 (Cathode) D6", "min": 0.67, "max": 1, "unit": "V"},
            {"description": "12. Pin4 (Anode) and Pin 1 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "13. Pin2 (Anode) and Pin 1 (Cathode)", "min": 0.85, "max": 1.1, "unit": "V"},
            {"description": "14. Pin3 (Anode) and Pin 1 (Cathode)", "min": 0.85, "max": 1.1, "unit": "V"},
            {"description": "15. Pin10 (Anode) and Pin 11 (Cathode)", "min": 0.5, "max": 0.8, "unit": "V"},
            {"description": "16. Pin11 (Anode) and Pin 12 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "17. Pin6 (Anode) and Pin 7 (Cathode)", "min": 0.5, "max": 0.8, "unit": "V"},
            {"description": "18. Pin7 (Anode) and Pin 1 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "19. Pin1 (Anode) and Pin 12 (Cathode)", "min": 0.9, "max": 1.2, "unit": "V"},
            {"description": "20. Pin5 (Anode) and Pin 2 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "21. Pin5 (Anode) and Pin 3 (Cathode)", "min": 0.6, "max": 1, "unit": "V"},
            {"description": "22. Pin2 (Anode) and Pin 1 (Cathode)", "min": 0.67, "max": 1, "unit": "V"},
            {"description": "23. Pin2 (Anode) and Pin 3 (Cathode)", "min": 1.2, "max": 1.5, "unit": "V"},
            {"description": "24. Pin5 (Anode) and Pin 6 (Cathode)", "min": 0.5, "max": 0.7, "unit": "V"},
            {"description": "25. Pin2 (Anode) and Pin 3 (Cathode)", "min": 1.2, "max": 1.5, "unit": "V"},
            {"description": "26. Pin5 (Anode) and Pin 6 (Cathode)", "min": 0.5, "max": 0.7, "unit": "V"},
            {"description": "27. Pin2 (Anode) and Pin 3 (Cathode)", "min": 1.2, "max": 1.5, "unit": "V"},
            {"description": "28. Pin5 (Anode) and Pin 6 (Cathode)", "min": 0.5, "max": 0.7, "unit": "V"},
            {"description": "29. Pin2 (Anode) and Pin 3 (Cathode)", "min": 1.2, "max": 1.5, "unit": "V"},
            {"description": "30. Pin5 (Anode) and Pin 6 (Cathode)", "min": 0.5, "max": 0.7, "unit": "V"},
            {"description": "31. Measure the resistance across the component - R2", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "32. Measure the resistance across the component - R8", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "33. Measure the resistance across the component - R1", "min": 0.8, "max": 1.1, "unit": "Ω"},
            {"description": "34. Measure the resistance across the component - R22", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "35. Measure the resistance across the component - R28", "min": 15.2, "max": 16, "unit": "Ω"},
            {"description": "36. Measure the resistance across the component - R21", "min": 0.8, "max": 1.1, "unit": "Ω"},
            {"description": "37. Measure the resistance across the component - R46", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "38. Measure the resistance across the component - R58", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "39. Measure the resistance across the component - R70", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "40. Measure the resistance across the component - R82", "min": 15.5, "max": 16, "unit": "Ω"},
            {"description": "41. Measure the resistance across the component - R34", "min": 0.8, "max": 1.1, "unit": "Ω"},
            {"description": "42. Measure the resistance across the component - R38", "min": 0.8, "max": 1.1, "unit": "Ω"},
            {"description": "43. Measure the capacitance across the component - C5", "min": 4e-06, "max": 5e-06, "unit": "F"},
            {"description": "44. Measure the capacitance across the component - C14", "min": 4e-06, "max": 5e-06, "unit": "F"},
        ],
    },
    "Bypass Capacitor B/D": {
        "prefix": "B",
        "digits": 4,
        "steps": [
            {"description": "01. Initial Capacitor Voltage", "min": 0, "max": 1, "unit": "V"},
            {"description": "02. Capacitor Voltage after 1 Time Constant", "min": 13, "max": 17, "unit": "V"},
            {"description": "03. Capacitor Voltage after 5 Time Constants", "min": 22, "max": 25, "unit": "V"},
            {"description": "04. Measured Capacitance", "min": 100, "max": 140, "unit": "mF"},
            {"description": "05. Capacitor Voltage with 15 V disconnected", "min": 19, "max": 25, "unit": "V"},
            {"description": "06. Capacitor Voltage after charge bleed", "min": 0, "max": 1, "unit": "V"},
        ],
    },
    "Tuning Capacitor B/D": {
        "prefix": "T",
        "digits": 4,
        "steps": [
            {"description": "01. Using a multimeter, measure the capacitance between A1 and ANT+ (See encircled in red below) and record it in the table against test index 1 on the Test Result Section. Base Capacitance Top", "min": 47, "max": 53, "unit": "μF"},
            {"description": "02. Using a multimeter, measure the capacitance between A1T and ANT+ (See encircled in red below) and record it in the table against test index 2 on the Test Result Section. Tuning Capacitance Top", "min": 56.43, "max": 62.37, "unit": "μF"},
            {"description": "03. Using a multimeter, measure the capacitance between A2 and ANT- (See encircled in red below) and record it in the table against test index 3 on the Test Result Section. Base Capacitance Bottom", "min": 47, "max": 53, "unit": "μF"},
            {"description": "04. Using a multimeter, measure the capacitance between A2T and ANT- (See encircled in red below) and record it in the table against test index 4 on the Test Result Section. Tuning Capacitance Bottom", "min": 56.43, "max": 62.37, "unit": "μF"},
            {"description": "05. Using a multimeter measure the resistance between TP9 and ANT+ (See encircled in red below) and record it in the table against test index 5 on the Test Result Section. Resistance between TP9 and ANT+", "min": 147, "max": 153, "unit": "kΩ"},
            {"description": "06. Using a multimeter, measure the resistance between TP10 and TP7 (See encircled in red below) and record it in the table against test index 6 on the Test Result Section. Resistance between TP10 and TP7", "min": 147, "max": 153, "unit": "kΩ"},
            {"description": "07. Using a LCR meter at Rp (resistance parallel setting), measure the resistance between TP3 and TP4 f = 2kHz(See encircled in red below) and record it in the table against test index 7 on the Test Result Section. Resistance between TP3 and TP4", "min": 600, "max": 610, "unit": "kΩ"},
        ],
    },
    "Controller B/D": {"prefix": "C", "digits": 4, "steps": []},
}

# 보드 라벨은 설정에서 자동 파생한다 — 목록을 두 곳에 두지 않아 누락을 막는다(단일 출처).
BOARD_LABELS = list(BOARD_CONFIG)

# 사용자 역할 표시 라벨 — 사이드바·관리자 화면에서 공용으로 사용한다.
ROLE_LABEL = {"admin": "🔴 관리자", "editor": "🟡 편집자", "viewer": "🟢 뷰어"}
