import altair as alt
import pandas as pd
import streamlit as st

from lib.constants import BOARD_COLOR, BOARD_CONFIG, BOARD_LABELS, COATING_STEPS
from lib.database import load_coating_records, load_movements, load_records

st.title("CG Progress")
st.caption('CG PCB 5종에 대한 "사전작업 진척도"를 표시합니다.')

# Serial 첫 글자(prefix) → 보드 라벨 매핑(BOARD_CONFIG에서 파생, 단일 출처). 입고·완료 metric·차트 lookup 공용.
PREFIX_TO_LABEL = {cfg["prefix"]: label for label, cfg in BOARD_CONFIG.items()}
# 차트 in-chart 매핑용 DataFrame(첫 글자 → 보드 라벨). PREFIX_TO_LABEL에서 파생.
prefix_labels = pd.DataFrame({"prefix": list(PREFIX_TO_LABEL), "board": list(PREFIX_TO_LABEL.values())})


def board_metrics(serials: pd.Series) -> None:
    """Serial 시리즈를 보드별로 세어 metric을 BOARD_COLOR 순서로 가로 배치한다(데이터 없는 보드는 0).
    입고수량·완료수량이 모두 'Serial을 보드별로 센다'는 같은 모양이라 한 함수로 공유한다.
    https://docs.streamlit.io/develop/api-reference/data/st.metric"""
    counts = serials.str[0].map(PREFIX_TO_LABEL).value_counts()
    for col, board in zip(st.columns(len(BOARD_COLOR)), BOARD_COLOR):
        col.metric(board, int(counts.get(board, 0)), border=True)


# ── PCBA In-Stock (입고수량) ──────────────────────────────
# 입고수량 = type='Inbound' 행 수(입출고 관리 페이지의 '입고수량' metric과 동일 기준). 보드는 Serial 첫 글자로 구분.
st.subheader("PCBA In-Stock")
movements = load_movements()
board_metrics(movements[movements["type"] == "Inbound"]["serial_number"])


def render_completion(records: pd.DataFrame, kind: str) -> None:
    """한 종류(기능 테스트/코팅)의 보드별 완료수량 metric + 완료 추이(누적 막대)를 그린다.
    두 테이블 모두 serial_number·test_datetime을 가져 동일 변환을 공유한다(verification.py와 같은 탭 구조)."""
    # 검수 완료(verify_by NOT NULL)된 데이터만 집계한다 — 검수 전(검수 중, verify_by IS NULL)인 건
    # metric·차트 어디에도 표시하지 않는다. 검수는 Serial 단위로 한 번에 처리되므로 행 필터로 충분하다.
    records = records[records["verify_by"].notna()]
    if records.empty:
        st.info("검수 완료된 데이터가 없습니다.")
        return

    # tidy: serial당 1행(여러 측정행은 같은 test_datetime이라 중복 제거). test_datetime은 날짜/날짜+시간이
    # 섞여 있어 앞 10자(YYYY-MM-DD)만 사용한다. 차트 '데이터 표시(표)'에도 이 두 컬럼만 그대로 보인다.
    tidy = (
        records.assign(test_date=pd.to_datetime(records["test_datetime"].str[:10], format="%Y-%m-%d")
                                   .dt.strftime("%Y-%m-%d"))
        [["test_date", "serial_number"]]
        .drop_duplicates()
        .sort_values(["test_date", "serial_number"])
        .reset_index(drop=True)
    )

    # 보드별 완료수량(코팅/테스트 끝낸 distinct Serial 수) metric.
    board_metrics(tidy["serial_number"])

    # 툴팁에 그 막대(날짜·보드)의 '모든' Serial을 보이려면 그룹별 목록이 필요하다. Vega-Lite엔 문자열을
    # 합치는 집계가 없으므로 (날짜, prefix)별 목록을 미리 만들어 합성키로 lookup해 붙인다(표엔 안 나옴).
    group_serials = (
        tidy.assign(prefix=tidy["serial_number"].str[0])
        .groupby(["test_date", "prefix"])["serial_number"]
        .apply(lambda s: ", ".join(sorted(s)))
        .reset_index(name="serials")
    )
    group_serials["key"] = group_serials["test_date"] + "|" + group_serials["prefix"]
    group_serials = group_serials[["key", "serials"]]

    # 그래프가 집계·매핑을 모두 수행한다: prefix→board(색), (날짜·보드)별 count()=완료수량(stack 누적),
    # 툴팁에 Serial 목록. x축 눈금은 labelExpr로 "May 04" 표기(데이터 타입을 안 바꿔 epoch 누수 없음).
    # https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart
    chart = (
        alt.Chart(tidy)
        .transform_calculate(prefix="substring(datum.serial_number, 0, 1)")
        .transform_lookup(lookup="prefix", from_=alt.LookupData(prefix_labels, "prefix", ["board"]))
        .transform_calculate(key="datum.test_date + '|' + datum.prefix")
        .transform_lookup(lookup="key", from_=alt.LookupData(group_serials, "key", ["serials"]))
        .mark_bar()
        .encode(
            x=alt.X("test_date:O", sort="ascending", title="테스트 날짜",
                    axis=alt.Axis(labelAngle=-45,
                                  labelExpr="utcFormat(toDate(datum.value), '%b %d')")),
            y=alt.Y("count():Q", title="완료 수량 (개)", stack=True),
            color=alt.Color("board:N", title="보드",
                            scale=alt.Scale(domain=list(BOARD_COLOR),
                                            range=list(BOARD_COLOR.values()))),
            detail=alt.Detail("serials:N"),
            tooltip=[alt.Tooltip("test_date:N", title="날짜"),
                     alt.Tooltip("board:N", title="보드"),
                     alt.Tooltip("count():Q", title="수량"),
                     alt.Tooltip("serials:N", title="번호")],
        )
    )
    # key로 element ID를 분리한다(탭마다 구조가 같은 차트라 충돌 방지).
    st.altair_chart(chart, width="stretch", key=f"{kind}_trend")


def render_value_explorer(records: pd.DataFrame, kind: str) -> None:
    """탭 하단: 보드와 STEP(기능)/POINT(코팅)를 골라 '검수 완료된' 측정값을 Serial별 라인차트로 본다.
    measurements는 TEXT라 숫자만 골라 그리고, 스펙의 min/max가 있으면 허용 기준선을 함께 표시한다."""
    records = records[records["verify_by"].notna()]
    st.divider()
    st.markdown("##### Trend of Measurements")

    bcol, icol = st.columns(2)
    board = bcol.selectbox("보드", BOARD_LABELS, key=f"{kind}_vx_board")
    cfg = BOARD_CONFIG[board]

    # 기능 테스트는 보드별 STEP(test_item=1..N), 코팅은 공통 POINT(coating_point=T1..B4)를 고른다.
    if kind == "func":
        item_col, pick_label = "test_item", "STEP"
        options = [{"value": str(i + 1), "label": s["description"], "spec": s}
                   for i, s in enumerate(cfg["steps"])]
    else:
        item_col, pick_label = "coating_point", "POINT"
        options = [{"value": s["point"], "label": s["point"], "spec": s} for s in COATING_STEPS]

    if not options:  # Controller 기능 테스트처럼 STEP이 없는 보드
        st.info("이 보드는 선택할 STEP이 없습니다.")
        return

    pick = icol.selectbox(pick_label, options, format_func=lambda o: o["label"], key=f"{kind}_vx_item")
    spec = pick["spec"]
    unit = spec.get("unit") or ""

    # 선택한 보드(prefix)·STEP/POINT의 검수완료 측정값만 숫자로 추려 Serial 순으로 그린다.
    sub = records[records["serial_number"].str.startswith(cfg["prefix"])
                  & (records[item_col] == pick["value"])].copy()
    sub["측정값"] = pd.to_numeric(sub["measurements"], errors="coerce")
    sub = sub.dropna(subset=["측정값"]).sort_values("serial_number")
    if sub.empty:
        st.info("검수된 측정값이 없습니다.")
        return

    # y축을 측정값에 맞추되(zero=False + 8% 여유), 스펙 기준선(min/max)이 데이터 범위 밖이면 그 값까지
    # 범위를 넓혀 기준선이 항상 보이게 한다(도메인 = 데이터 범위 ∪ min/max). 이상치·편차도 함께 드러난다.
    vals = sub["측정값"]
    bounds = [spec[b] for b in ("min", "max") if spec.get(b) is not None]
    lo_d = min([float(vals.min())] + bounds)
    hi_d = max([float(vals.max())] + bounds)
    span = hi_d - lo_d
    pad = span * 0.08 if span else (abs(hi_d) * 0.08 or 1.0)
    y_scale = alt.Scale(domain=[lo_d - pad, hi_d + pad], zero=False)

    y_title = f"측정값 ({unit})" if unit else "측정값"
    # 라인(선·점) 색은 #001685. point=True는 선 색을 안 따라가므로 점 색을 따로 지정한다.
    # x축 눈금 라벨은 숨긴다(Serial이 많아 잡음 — 어느 Serial인지는 툴팁으로 확인).
    line = alt.Chart(sub).mark_line(clip=True, color="#001685",
                                    point=alt.OverlayMarkDef(color="#001685")).encode(
        x=alt.X("serial_number:N", sort="ascending", title="Serial", axis=alt.Axis(labels=False)),
        y=alt.Y("측정값:Q", title=y_title, scale=y_scale),
        tooltip=[alt.Tooltip("serial_number:N", title="번호"),
                 alt.Tooltip("측정값:Q", title="측정")],
    )
    # 스펙 min/max 허용 기준선(점선). 위에서 도메인에 포함했으므로 항상 보인다.
    layers = [line]
    for bound in ("min", "max"):
        if spec.get(bound) is not None:
            layers.append(alt.Chart(pd.DataFrame({"y": [spec[bound]]}))
                          .mark_rule(color="#888888", strokeDash=[4, 4])
                          .encode(y=alt.Y("y:Q", scale=y_scale)))
    st.altair_chart(alt.layer(*layers), width="stretch", key=f"{kind}_vx_chart")


# ── Completion Trend: 종류별 탭 ───────────────────────────
# verification.py와 같은 'SOURCES 리스트 + 탭' 구조. 표/집계 로직은 render_* 함수가 공유한다.
SOURCES = [
    {"kind": "func", "title": "Functional Test", "load": load_records},
    {"kind": "coat", "title": "Conformal Coating", "load": load_coating_records},
]
st.subheader("Completion Trend")
for tab, src in zip(st.tabs([s["title"] for s in SOURCES]), SOURCES):
    with tab:
        records = src["load"]()
        render_completion(records, src["kind"])
        render_value_explorer(records, src["kind"])
