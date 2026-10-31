"""
database/db.py
Handles the SQLite connection and creates the tables from schema.sql.
"""

import sqlite3
from pathlib import Path

from config import DB_PATH, SCHEMA_PATH


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the database.
    Rows come back as dictionary-like objects, so you can write row["full_name"].
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """
    Create all tables from schema.sql.
    Safe to call every time the app starts, because the schema uses IF NOT EXISTS.
    """
    schema_sql = Path(SCHEMA_PATH).read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Run a SELECT and return every matching row."""
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Run a SELECT and return the first matching row, or None."""
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """
    Run an INSERT, UPDATE, or DELETE and save it.
    Returns the id of the last inserted row (useful after an INSERT).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()