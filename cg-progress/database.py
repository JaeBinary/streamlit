import sqlite3
import streamlit as st
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "cg_progress.db"
DB_PATH.parent.mkdir(exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _meas(m) -> str | None:
    """측정값을 정규화한다. 미입력(빈 문자열·공백·None)은 빈 문자열이 아니라
    NULL로 저장한다. (예: 미측정 스텝 → measurements IS NULL)"""
    if m is None:
        return None
    s = str(m).strip()
    return s if s else None


# 커넥션은 직렬화 불가능한 전역 리소스이므로 cache_resource로 1회만 생성한다.
# https://docs.streamlit.io/develop/concepts/architecture/caching
@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS PCBA_Functional_test (
            serial_number   TEXT NOT NULL,
            test_item       TEXT NOT NULL,
            measurements    TEXT,
            test_datetime   TEXT NOT NULL,
            test_By         TEXT NOT NULL,
            verify_datetime TEXT,
            verify_by       TEXT,
            PRIMARY KEY (serial_number, test_item)
        )
    """)
    # 컨포멀 코팅: Serial마다 코팅 포인트(TOP-1~4, BOTTOM-1~4)별 두께를 측정한다.
    # 구조는 기능 테스트와 동일(검수 흐름 공유) — test_item 대신 coating_point가 복합키의 일부다.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS PCBA_Conformal_Coating (
            serial_number   TEXT NOT NULL,
            coating_point   TEXT NOT NULL,
            measurements    TEXT,
            test_datetime   TEXT,
            test_by         TEXT,
            verify_datetime TEXT,
            verify_by       TEXT,
            PRIMARY KEY (serial_number, coating_point)
        )
    """)
    # oid: Entra(Azure AD) 사용자 객체 ID. 테넌트 내 불변·재사용 불가라 데이터 저장 키로 적합하다.
    # (email·name은 변경 가능하므로 키로 쓰지 않는다 — Microsoft 문서 권장)
    # https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference
    # status: 계정 상태 Enable(사용)·Disable(비활성). 기본 Enable.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            oid           TEXT PRIMARY KEY,
            status        TEXT NOT NULL DEFAULT 'Enable',
            email         TEXT,
            name          TEXT,
            role          TEXT NOT NULL DEFAULT 'viewer',
            join_datetime TEXT
        )
    """)
    # PCBA 입출고 이력. serial_number가 PK(Serial당 1행) — type은 Inbound/Outbound.
    # verify_by: 등록한 사용자의 불변 oid(레거시 행은 이름 문자열 '이진수'). 화면 표시 시 oid→이름 변환.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS PCBA_Movement (
            serial_number TEXT NOT NULL,
            manufacturer  TEXT NOT NULL,
            type          TEXT NOT NULL,
            date          TEXT NOT NULL,
            verify_by     TEXT NOT NULL,
            PRIMARY KEY (serial_number)
        )
    """)
    # verify_by IS NULL(검수 중) 조회를 돕도록 인덱스를 둔다.
    # (Users.oid는 PRIMARY KEY라 자동 인덱스가 생성된다. email 조회는 사용자 수가 적어 인덱스 불필요)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_verify_by ON PCBA_Functional_test(verify_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_coating_verify_by ON PCBA_Conformal_Coating(verify_by)")
    conn.commit()
    return conn


# ── Users ─────────────────────────────────────────────────

def get_or_create_user(oid: str, email: str, name: str) -> tuple[str, str]:
    """oid(PK)로 사용자를 식별해 (role, status)를 반환한다. 없으면 생성한다.
    oid가 비어 있던 레거시 행(email만 있던 기존 사용자)은 첫 로그인 시 oid를 채워 재사용한다."""
    conn = get_conn()
    with conn:
        # 1) oid로 우선 조회 (정상 경로). 표시 이름·이메일은 매 로그인 시 최신값으로 갱신한다.
        #    records의 test_By·verify_by에는 불변 oid를 저장하므로, AD에서 이름이 바뀌어도
        #    매핑은 끊기지 않고 화면에는 최신 이름이 나온다.
        row = conn.execute("SELECT role, name, email, status FROM Users WHERE oid=?", (oid,)).fetchone()
        if row:
            if (name, email) != (row[1], row[2]):
                conn.execute("UPDATE Users SET name=?, email=? WHERE oid=?", (name, email, oid))
                user_names.clear()
            return row[0], row[3]
        # 2) 레거시 행 흡수: oid가 NULL이던 동일 email 행이 있으면 oid를 채워 재사용(중복 생성 방지).
        legacy = conn.execute(
            "SELECT role, status FROM Users WHERE oid IS NULL AND email=?", (email,)
        ).fetchone()
        if legacy:
            conn.execute(
                "UPDATE Users SET oid=?, name=? WHERE oid IS NULL AND email=?",
                (oid, name, email),
            )
            return legacy[0], legacy[1]
        # 3) 신규 사용자: 첫 사용자 → admin, 이후 → viewer. status는 기본값 Enable.
        count = conn.execute("SELECT COUNT(*) FROM Users").fetchone()[0]
        role = "admin" if count == 0 else "viewer"
        conn.execute(
            "INSERT INTO Users (oid, email, name, role, join_datetime) VALUES (?,?,?,?,?)",
            (oid, email, name, role, _now()),
        )
        user_names.clear()
        return role, "Enable"

@st.cache_data(ttl=300)
def load_users() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(
        "SELECT oid, email, name, role, status, join_datetime FROM Users ORDER BY join_datetime",
        conn,
    )

def update_user(email: str, name: str, role: str, status: str):
    """email로 사용자를 찾아 name·role·status를 갱신한다. (관리자 화면 인라인 편집용)
    PK는 oid이지만 email도 사용자별 고유하므로 편집 키로 그대로 사용한다."""
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE Users SET name=?, role=?, status=? WHERE email=?",
            (name, role, status, email),
        )
    load_users.clear()
    user_names.clear()  # 이름이 바뀌면 oid→이름 매핑도 무효화


@st.cache_data(ttl=300)
def user_names() -> dict:
    """oid → 표시 이름 매핑. records의 test_By·verify_by(oid 저장)를 화면에 이름으로
    바꿔 표시할 때 쓴다. oid를 못 찾으면(레거시 행·미등록) 호출부에서 저장값 그대로 폴백한다."""
    conn = get_conn()
    rows = conn.execute("SELECT oid, name FROM Users WHERE oid IS NOT NULL").fetchall()
    return {oid: name for oid, name in rows}


# ── Records (기능 테스트 · 코팅 공용) ─────────────────────
# 두 테이블은 검수 흐름·경합 가드가 동일하고 (테이블, item 컬럼, tester 컬럼)만 다르다.
# 아래 프라이빗 헬퍼가 그 차이를 인자로 받아 한 번에 처리하고, 공개 함수는 테이블별 인자만
# 채워 위임한다. 컬럼명(test_item/coating_point, test_By/test_by)은 라이브 DB 스키마라 그대로 쓴다.

def _insert(table: str, item_col: str, tester_col: str, rows: list, load_fn):
    """rows: list of (serial, item, test_datetime, tester, measurements). 한 번에 여러 건 저장한다.
    test_datetime은 'YYYY-MM-DD HH:MM:SS' 문자열. 저장 시 verify_*는 NULL(=검수 중)로 둔다 —
    관리자가 승인하면 채워진다. 복합키(serial, item)가 겹치면 덮어쓴다(INSERT OR REPLACE → 재검수)."""
    conn = get_conn()
    with conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO {table}"
            f" (serial_number, {item_col}, measurements, test_datetime, {tester_col}, verify_datetime, verify_by)"
            " VALUES (?,?,?,?,?,NULL,NULL)",
            [(str(s), str(it), _meas(m), str(d), str(tb)) for s, it, d, tb, m in rows],
        )
    load_fn.clear()

def _verify(table: str, serial, verify_by, load_fn) -> int:
    """해당 Serial의 '검수 중'(verify_by IS NULL) 행만 승인 처리한다(verify_datetime=현재시각, verify_by=승인자 oid).
    이미 처리/삭제되어 대상이 없으면 0을 반환한다 — 동시 접속 중 중복 처리(경합)를 막는 가드."""
    conn = get_conn()
    with conn:
        cur = conn.execute(
            f"UPDATE {table} SET verify_datetime=?, verify_by=? WHERE serial_number=? AND verify_by IS NULL",
            (_now(), str(verify_by), str(serial)),
        )
    load_fn.clear()
    return cur.rowcount

def _delete_pending(table: str, tester_col: str, serial, owner_oid, load_fn) -> int:
    """'검수 중'(verify_by IS NULL) 행만 삭제한다 — 검수 리스트의 반려(관리자)·취소(편집자)용.
    owner_oid를 주면 본인 요청분({tester_col}=oid)으로 제한한다(편집자). 대상이 없으면 0(경합 가드)."""
    conn = get_conn()
    sql = f"DELETE FROM {table} WHERE serial_number=? AND verify_by IS NULL"
    params = [str(serial)]
    if owner_oid is not None:
        sql += f" AND {tester_col}=?"
        params.append(str(owner_oid))
    with conn:
        cur = conn.execute(sql, params)
    load_fn.clear()
    return cur.rowcount

def _delete_serial(table: str, serial, load_fn):
    """해당 Serial의 모든 행을 삭제한다(상태 무관 — Raw Data의 관리자 삭제용)."""
    conn = get_conn()
    with conn:
        conn.execute(f"DELETE FROM {table} WHERE serial_number=?", (str(serial),))
    load_fn.clear()


# ── 기능 테스트 ───────────────────────────────────────────

@st.cache_data(ttl=60)
def load_records() -> pd.DataFrame:
    """모든 레코드를 조회한다(전체 공개). verify_by/verify_datetime이 NULL이면 '검수 중'이다."""
    conn = get_conn()
    # test_item은 '1'~'25' 문자열이므로 숫자 순으로 정렬한다.
    return pd.read_sql(
        "SELECT * FROM PCBA_Functional_test ORDER BY CAST(test_item AS INTEGER), serial_number", conn)

def insert_records(rows: list):
    """rows: list of (serial, test_item, test_datetime, tested_by, measurements)."""
    _insert("PCBA_Functional_test", "test_item", "test_By", rows, load_records)

def verify_serial(serial, verify_by) -> int:
    return _verify("PCBA_Functional_test", serial, verify_by, load_records)

def delete_pending(serial, owner_oid=None) -> int:
    return _delete_pending("PCBA_Functional_test", "test_By", serial, owner_oid, load_records)

def delete_serial(serial):
    _delete_serial("PCBA_Functional_test", serial, load_records)


# ── 컨포멀 코팅 ───────────────────────────────────────────
# test_item → coating_point, test_By → test_by 만 다르고 흐름은 기능 테스트와 동일하다.

@st.cache_data(ttl=60)
def load_coating_records() -> pd.DataFrame:
    """모든 코팅 레코드를 조회한다(전체 공개). verify_by/verify_datetime이 NULL이면 '검수 중'이다."""
    conn = get_conn()
    return pd.read_sql("SELECT * FROM PCBA_Conformal_Coating ORDER BY serial_number, coating_point", conn)

def insert_coating_records(rows: list):
    """rows: list of (serial, coating_point, test_datetime, test_by, measurements)."""
    _insert("PCBA_Conformal_Coating", "coating_point", "test_by", rows, load_coating_records)

def verify_coating_serial(serial, verify_by) -> int:
    return _verify("PCBA_Conformal_Coating", serial, verify_by, load_coating_records)

def delete_coating_pending(serial, owner_oid=None) -> int:
    return _delete_pending("PCBA_Conformal_Coating", "test_by", serial, owner_oid, load_coating_records)

def delete_coating_serial(serial):
    _delete_serial("PCBA_Conformal_Coating", serial, load_coating_records)


# ── Movement (입출고) ─────────────────────────────────────
# serial_number가 PK라 Serial당 1행(최신 입·출고 상태)이다 — 재등록은 기존 행을 덮어쓴다.

@st.cache_data(ttl=60)
def load_movements() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(
        "SELECT serial_number, manufacturer, type, date, verify_by FROM PCBA_Movement"
        " ORDER BY date DESC, serial_number",
        conn,
    )

def add_movement_batch(prefix: str, digits: int, manufacturer: str,
                       mtype: str, date: str, qty: int, verify_by: str) -> list[str]:
    """선택한 보드(prefix)의 PCBA_Movement 기존 최대 번호 다음부터 qty개의 serial을 순차 생성해 저장한다.
    예: 해당 보드에 H0020까지 있으면 qty=10 → H0021~H0030. 빈 보드면 0001부터.
    verify_by에는 등록한 사용자의 불변 oid를 저장한다(화면 표시 시 oid→현재 이름으로 변환).
    생성된 serial 목록을 반환한다."""
    conn = get_conn()
    with conn:
        rows = conn.execute(
            "SELECT serial_number FROM PCBA_Movement WHERE serial_number LIKE ?",
            (prefix + "%",),
        ).fetchall()
        # prefix 뒤 숫자부만 취해 최대값을 찾는다(형식이 어긋난 행은 건너뛴다).
        max_num = 0
        for (s,) in rows:
            tail = s[len(prefix):]
            if tail.isdigit():
                max_num = max(max_num, int(tail))
        serials = [f"{prefix}{n:0{digits}d}" for n in range(max_num + 1, max_num + 1 + qty)]
        conn.executemany(
            "INSERT INTO PCBA_Movement (serial_number, manufacturer, type, date, verify_by) VALUES (?,?,?,?,?)",
            [(s, str(manufacturer), str(mtype), str(date), str(verify_by)) for s in serials],
        )
    load_movements.clear()
    return serials

def outbound_serial(serial: str, date: str, verify_by: str) -> int:
    """입고된(type='Inbound') Serial을 출고 처리한다 — type='Outbound', date·verify_by를 갱신한다.
    출고는 새 번호를 채번하지 않고 기존 입고 Serial의 상태만 전환한다(serial_number가 PK라 1행 유지).
    이미 출고됐거나 대상이 없으면 0을 반환한다 — 동시 처리(경합)를 막는 가드."""
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "UPDATE PCBA_Movement SET type='Outbound', date=?, verify_by=?"
            " WHERE serial_number=? AND type='Inbound'",
            (str(date), str(verify_by), str(serial)),
        )
    load_movements.clear()
    return cur.rowcount

def delete_movement(serial: str):
    """해당 Serial의 입출고 행을 삭제한다(Raw Data의 관리자 삭제용)."""
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM PCBA_Movement WHERE serial_number=?", (str(serial),))
    load_movements.clear()
