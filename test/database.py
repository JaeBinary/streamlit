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
            serial        TEXT NOT NULL,
            test_item     TEXT NOT NULL,
            measurements  TEXT,
            test_date     TEXT NOT NULL,
            tested_by     TEXT NOT NULL,
            save_datetime TEXT,
            saved_by      TEXT,
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
    # saved_by는 뷰어/편집자 조회 시 필터 조건이므로 인덱스를 둔다.
    # (users.email은 PRIMARY KEY라 자동 인덱스가 생성되어 별도 인덱스가 불필요)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_saved_by ON test_results(saved_by)")
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

def update_role(email: str, role: str):
    conn = get_conn()
    with conn:
        conn.execute("UPDATE users SET role=? WHERE email=?", (role, email))
    load_users.clear()


# ── Records ───────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_records(user_email: str, role: str) -> pd.DataFrame:
    conn = get_conn()
    # test_item은 '1'~'25' 문자열이므로 숫자 순으로 정렬한다.
    order = "ORDER BY CAST(test_item AS INTEGER), serial"
    if role == "admin":
        return pd.read_sql(f"SELECT * FROM test_results {order}", conn)
    return pd.read_sql(
        f"SELECT * FROM test_results WHERE saved_by=? {order}",
        conn, params=(user_email,),
    )

def insert_records(rows: list, user_email: str):
    """rows: list of (serial, test_item, test_date, tested_by, measurements). 한 번에 여러 건 저장.
    (serial, test_item) 복합키가 겹치면 기존 행을 덮어쓴다(INSERT OR REPLACE)."""
    now = _now()
    conn = get_conn()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO test_results"
            " (serial, test_item, measurements, test_date, tested_by, save_datetime, saved_by)"
            " VALUES (?,?,?,?,?,?,?)",
            [(str(s), str(ti), _meas(m), str(d), str(tb), now, str(user_email))
             for s, ti, d, tb, m in rows],
        )
    load_records.clear()

def delete_serial(serial):
    """해당 Serial의 모든 test_item 행을 삭제한다."""
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM test_results WHERE serial=?", (str(serial),))
    load_records.clear()
