"""summaries テーブルのスキーマ定義とマイグレーション.

書き込み側 (``digest/sink.py``) と読み出し側 (``repositories/sqlite.py``) の
双方が同じ DDL を必要とするため、ここへ一元化する。
"""
from __future__ import annotations

import sqlite3

CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS summaries ("
    "id TEXT PRIMARY KEY, pdf_path TEXT, pdf_hash TEXT, page_count INTEGER, "
    "summary TEXT, length TEXT, model TEXT, created_at TEXT, "
    "tokens_in INTEGER, tokens_out INTEGER, latency_ms INTEGER)"
)

# v0.2.1 以前に作られた DB には存在しないカラム。
# CREATE TABLE IF NOT EXISTS は既存テーブルには何もしないので、
# 不足分を ALTER TABLE で個別に追加する (既存行の値は NULL のまま)。
_ADDED_COLUMNS: dict[str, str] = {
    "tokens_in": "INTEGER",
    "tokens_out": "INTEGER",
    "latency_ms": "INTEGER",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    """summaries テーブルを作成し、不足しているカラムを追加する."""
    conn.execute(CREATE_TABLE)
    existing = {str(row[1]) for row in conn.execute("PRAGMA table_info(summaries)")}
    for column, sql_type in _ADDED_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE summaries ADD COLUMN {column} {sql_type}")
    conn.commit()
