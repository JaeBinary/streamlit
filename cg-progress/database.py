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
    # oid: Entra(Azure AD) 사용자 객체 ID. 테넌트 내 불변·재사용 불가라 데이터 저장 키로 적합하다.
    # (email·name은 변경 가능하므로 키로 쓰지 않는다 — Microsoft 문서 권장)
    # https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            oid                   TEXT PRIMARY KEY,
            email                 TEXT,
            name                  TEXT,
            role                  TEXT NOT NULL DEFAULT 'viewer',
            date_first_registered TEXT
        )
    """)
    # verify_by IS NULL(검수 중) 조회를 돕도록 인덱스를 둔다.
    # (users.oid는 PRIMARY KEY라 자동 인덱스가 생성된다. email 조회는 사용자 수가 적어 인덱스 불필요)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_verify_by ON PCBA_Functional_test(verify_by)")
    conn.commit()
    return conn


# ── Users ─────────────────────────────────────────────────

def get_or_create_user(oid: str, email: str, name: str) -> str:
    """oid(PK)로 사용자를 식별해 role을 반환한다. 없으면 생성한다.
    oid가 비어 있던 레거시 행(email만 있던 기존 사용자)은 첫 로그인 시 oid를 채워 재사용한다."""
    conn = get_conn()
    with conn:
        # 1) oid로 우선 조회 (정상 경로). 표시 이름·이메일은 매 로그인 시 최신값으로 갱신한다.
        #    records의 test_By·verify_by에는 불변 oid를 저장하므로, AD에서 이름이 바뀌어도
        #    매핑은 끊기지 않고 화면에는 최신 이름이 나온다.
        row = conn.execute("SELECT role, name, email FROM users WHERE oid=?", (oid,)).fetchone()
        if row:
            if (name, email) != (row[1], row[2]):
                conn.execute("UPDATE users SET name=?, email=? WHERE oid=?", (name, email, oid))
                user_names.clear()
            return row[0]
        # 2) 레거시 행 흡수: oid가 NULL이던 동일 email 행이 있으면 oid를 채워 재사용(중복 생성 방지).
        legacy = conn.execute(
            "SELECT role FROM users WHERE oid IS NULL AND email=?", (email,)
        ).fetchone()
        if legacy:
            conn.execute(
                "UPDATE users SET oid=?, name=? WHERE oid IS NULL AND email=?",
                (oid, name, email),
            )
            return legacy[0]
        # 3) 신규 사용자: 첫 사용자 → admin, 이후 → viewer.
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        role = "admin" if count == 0 else "viewer"
        conn.execute(
            "INSERT INTO users (oid, email, name, role, date_first_registered) VALUES (?,?,?,?,?)",
            (oid, email, name, role, _now()),
        )
        user_names.clear()
        return role

@st.cache_data(ttl=300)
def load_users() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(
        "SELECT email, name, role, date_first_registered FROM users ORDER BY date_first_registered",
        conn,
    )

def update_user(email: str, name: str, role: str):
    """email로 사용자를 찾아 name·role을 갱신한다. (관리자 화면 인라인 편집용)
    PK는 oid이지만 email도 사용자별 고유하므로 편집 키로 그대로 사용한다."""
    conn = get_conn()
    with conn:
        conn.execute("UPDATE users SET name=?, role=? WHERE email=?", (name, role, email))
    load_users.clear()
    user_names.clear()  # 이름이 바뀌면 oid→이름 매핑도 무효화


@st.cache_data(ttl=300)
def user_names() -> dict:
    """oid → 표시 이름 매핑. records의 test_By·verify_by(oid 저장)를 화면에 이름으로
    바꿔 표시할 때 쓴다. oid를 못 찾으면(레거시 행·미등록) 호출부에서 저장값 그대로 폴백한다."""
    conn = get_conn()
    rows = conn.execute("SELECT oid, name FROM users WHERE oid IS NOT NULL").fetchall()
    return {oid: name for oid, name in rows}


# ── Records ───────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_records() -> pd.DataFrame:
    """모든 레코드를 조회한다(전체 공개). verify_by/verify_datetime이 NULL이면 '검수 중'이다."""
    conn = get_conn()
    # test_item은 '1'~'25' 문자열이므로 숫자 순으로 정렬한다.
    order = "ORDER BY CAST(test_item AS INTEGER), serial_number"
    return pd.read_sql(f"SELECT * FROM PCBA_Functional_test {order}", conn)

def insert_records(rows: list):
    """rows: list of (serial, test_item, test_datetime, tested_by, measurements). 한 번에 여러 건 저장.
    test_datetime은 'YYYY-MM-DD HH:MM:SS' 형식 문자열(값은 시각까지, 표시는 호출부에서 date만).
    저장 시 verify_datetime/verify_by는 NULL(=검수 중)로 둔다 — 관리자가 검수 리스트에서 승인하면 채워진다.
    (serial, test_item) 복합키가 겹치면 기존 행을 덮어쓴다(INSERT OR REPLACE → 재저장 시 다시 검수 중)."""
    conn = get_conn()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO PCBA_Functional_test"
            " (serial_number, test_item, measurements, test_datetime, test_By, verify_datetime, verify_by)"
            " VALUES (?,?,?,?,?,NULL,NULL)",
            [(str(s), str(ti), _meas(m), str(d), str(tb)) for s, ti, d, tb, m in rows],
        )
    load_records.clear()

def verify_serial(serial, verify_by):
    """해당 Serial의 '검수 중'(verify_by IS NULL) 행만 승인 처리한다(verify_datetime=현재시각, verify_by=승인자 oid).
    이미 승인되었거나 삭제되어 대상이 없으면 0을 반환한다 — 동시 접속 시 중복 처리(경합)를 막는 가드.
    반환값(영향 행 수)으로 호출부가 실제 처리 여부를 판단한다."""
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "UPDATE PCBA_Functional_test SET verify_datetime=?, verify_by=? WHERE serial_number=? AND verify_by IS NULL",
            (_now(), str(verify_by), str(serial)),
        )
    load_records.clear()
    return cur.rowcount

def delete_pending(serial, owner_oid=None):
    """'검수 중'(verify_by IS NULL)인 행만 삭제한다 — 검수 리스트의 반려(관리자)·취소(편집자)용.
    owner_oid를 주면 본인이 요청한 건(tested_by=oid)으로 제한한다(편집자). 이미 승인/삭제되어 대상이
    없으면 0을 반환한다 — 동시 접속 시 이미 처리된 건을 잘못 삭제하는 것을 막는 경합 가드."""
    conn = get_conn()
    sql = "DELETE FROM PCBA_Functional_test WHERE serial_number=? AND verify_by IS NULL"
    params = [str(serial)]
    if owner_oid is not None:
        sql += " AND test_By=?"
        params.append(str(owner_oid))
    with conn:
        cur = conn.execute(sql, params)
    load_records.clear()
    return cur.rowcount

def delete_serial(serial):
    """해당 Serial의 모든 test_item 행을 삭제한다(상태 무관 — Raw Data의 관리자 삭제용)."""
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM PCBA_Functional_test WHERE serial_number=?", (str(serial),))
    load_records.clear()
