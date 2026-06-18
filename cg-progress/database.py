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
        CREATE TABLE IF NOT EXISTS test_results (
            serial          TEXT NOT NULL,
            test_item       TEXT NOT NULL,
            measurements    TEXT,
            test_datetime   TEXT NOT NULL,
            tested_by       TEXT NOT NULL,
            verify_datetime TEXT,
            verify_by       TEXT,
            PRIMARY KEY (serial, test_item)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email                 TEXT PRIMARY KEY,
            name                  TEXT,
            role                  TEXT NOT NULL DEFAULT 'viewer',
            date_first_registered TEXT
        )
    """)
    # verify_by IS NULL(검수 중) 조회를 돕도록 인덱스를 둔다.
    # (users.email은 PRIMARY KEY라 자동 인덱스가 생성되어 별도 인덱스가 불필요)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_verify_by ON test_results(verify_by)")
    conn.commit()
    return conn


# ── Users ─────────────────────────────────────────────────

def get_or_create_user(email: str, name: str) -> str:
    conn = get_conn()
    with conn:
        row = conn.execute("SELECT role FROM users WHERE email=?", (email,)).fetchone()
        if row:
            return row[0]
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        role = "admin" if count == 0 else "viewer"
        conn.execute(
            "INSERT INTO users (email, name, role, date_first_registered) VALUES (?,?,?,?)",
            (email, name, role, _now()),
        )
        return role

@st.cache_data(ttl=300)
def load_users() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(
        "SELECT email, name, role, date_first_registered FROM users ORDER BY date_first_registered",
        conn,
    )

def update_user(email: str, name: str, role: str):
    """email(PK)로 사용자를 찾아 name·role을 갱신한다. (관리자 화면 인라인 편집용)"""
    conn = get_conn()
    with conn:
        conn.execute("UPDATE users SET name=?, role=? WHERE email=?", (name, role, email))
    load_users.clear()


# ── Records ───────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_records() -> pd.DataFrame:
    """모든 레코드를 조회한다(전체 공개). verify_by/verify_datetime이 NULL이면 '검수 중'이다."""
    conn = get_conn()
    # test_item은 '1'~'25' 문자열이므로 숫자 순으로 정렬한다.
    order = "ORDER BY CAST(test_item AS INTEGER), serial"
    return pd.read_sql(f"SELECT * FROM test_results {order}", conn)

def insert_records(rows: list):
    """rows: list of (serial, test_item, test_datetime, tested_by, measurements). 한 번에 여러 건 저장.
    test_datetime은 'YYYY-MM-DD HH:MM:SS' 형식 문자열(값은 시각까지, 표시는 호출부에서 date만).
    저장 시 verify_datetime/verify_by는 NULL(=검수 중)로 둔다 — 관리자가 검수 리스트에서 승인하면 채워진다.
    (serial, test_item) 복합키가 겹치면 기존 행을 덮어쓴다(INSERT OR REPLACE → 재저장 시 다시 검수 중)."""
    conn = get_conn()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO test_results"
            " (serial, test_item, measurements, test_datetime, tested_by, verify_datetime, verify_by)"
            " VALUES (?,?,?,?,?,NULL,NULL)",
            [(str(s), str(ti), _meas(m), str(d), str(tb)) for s, ti, d, tb, m in rows],
        )
    load_records.clear()

def verify_serial(serial, verify_by):
    """해당 Serial의 모든 test_item을 승인 처리한다(verify_datetime=현재시각, verify_by=승인자 이메일)."""
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE test_results SET verify_datetime=?, verify_by=? WHERE serial=?",
            (_now(), str(verify_by), str(serial)),
        )
    load_records.clear()

def delete_serial(serial):
    """해당 Serial의 모든 test_item 행을 삭제한다."""
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM test_results WHERE serial=?", (str(serial),))
    load_records.clear()
