"""여러 페이지가 공유하는 상수 모음.

라벨이 여러 파일에 흩어져 복사되면 추가/이름 변경 시 누락이 생기므로 한곳에 모은다.
"""

# CG PCBA 5종 보드 라벨 — 기능 테스트·컨포멀 코팅 탭에서 공용으로 사용한다.
BOARD_LABELS = [
    "H-Bridge B/D",
    "Gate Driver B/D",
    "Bypass Capacitor B/D",
    "Tuning Capacitor B/D",
    "Controller B/D",
]

# 사용자 역할 표시 라벨 — 사이드바·관리자 화면에서 공용으로 사용한다.
ROLE_LABEL = {"admin": "🔴 관리자", "editor": "🟡 편집자", "viewer": "🟢 뷰어"}
