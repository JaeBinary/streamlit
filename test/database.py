import sqlite3
import streamlit as st
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "cg_progress.db"
DB_PATH.parent.mkdir(exist_ok=True)


@st.cache_resource
def _init_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id           INTEGER PRIMARY KEY,
            serial       TEXT    NOT NULL,
            test_date    TEXT    NOT NULL,
            test_by      TEXT    NOT NULL,
            test_item    TEXT    NOT NULL,
            measurements TEXT,
            saved_by     TEXT,
            created_at   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email                TEXT PRIMARY KEY,
            name                 TEXT,
            role                 TEXT NOT NULL DEFAULT 'viewer',
            date_first_registered TEXT
        )
    """)
    try:
        conn.execute("ALTER TABLE records ADD COLUMN created_at TEXT")
    except sqlite3.OperationalError:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_saved_by ON records(saved_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.commit()
    return conn


def get_conn() -> sqlite3.Connection:
    return _init_conn()


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
            (email, name, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
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
    if role == "admin":
        return pd.read_sql("SELECT * FROM records ORDER BY id", conn)
    return pd.read_sql(
        "SELECT * FROM records WHERE saved_by=? ORDER BY id",
        conn, params=(user_email,),
    )

def insert_record(serial, test_date, test_by, test_item, measurements, user_email):
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO records (serial, test_date, test_by, test_item, measurements, saved_by, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (str(serial), str(test_date), str(test_by), str(test_item), str(measurements),
             str(user_email), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    load_records.clear()

def bulk_update_records(updates: list):
    """updates: list of (row_id, serial, test_date, test_by, test_item, measurements)"""
    conn = get_conn()
    with conn:
        conn.executemany(
            "UPDATE records SET serial=?, test_date=?, test_by=?, test_item=?, measurements=? WHERE id=?",
            [(str(s), str(d), str(b), str(i), str(m), int(rid)) for rid, s, d, b, i, m in updates],
        )
    load_records.clear()

def delete_record(row_id):
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM records WHERE id=?", (row_id,))
    load_records.clear()

def clear_records(user_email: str, role: str):
    conn = get_conn()
    with conn:
        if role == "admin":
            conn.execute("DELETE FROM records")
        else:
            conn.execute("DELETE FROM records WHERE saved_by=?", (user_email,))
    load_records.clear()
