"""db.ensure_schema のユニットテスト (issue #21 のマイグレーション)"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pdfsum.db import ensure_schema

# v0.2.1 以前のスキーマ (tokens_in / tokens_out / latency_ms 無し)
_LEGACY_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS summaries ("
    "id TEXT PRIMARY KEY, pdf_path TEXT, pdf_hash TEXT, page_count INTEGER, "
    "summary TEXT, length TEXT, model TEXT, created_at TEXT)"
)
_LEGACY_INSERT = "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?)"

_NEW_COLUMNS = ("tokens_in", "tokens_out", "latency_ms")


def _columns(conn: sqlite3.Connection) -> list[str]:
    return [str(row[1]) for row in conn.execute("PRAGMA table_info(summaries)")]


def _make_legacy_db(db_path: Path, *, with_row: bool = False) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(_LEGACY_CREATE_TABLE)
    if with_row:
        conn.execute(
            _LEGACY_INSERT,
            (
                "old-id",
                "/a.pdf",
                "hash",
                3,
                "旧要約",
                "standard",
                "old-model",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    conn.commit()
    conn.close()


class TestEnsureSchema:
    def test_creates_table_with_all_columns(self, tmp_path: Path) -> None:
        """新規 DB では全カラムを持つテーブルが作られる"""
        conn = sqlite3.connect(str(tmp_path / "new.db"))

        ensure_schema(conn)

        columns = _columns(conn)
        for column in _NEW_COLUMNS:
            assert column in columns

    def test_adds_missing_columns_to_legacy_db(self, tmp_path: Path) -> None:
        """既存 DB (旧スキーマ) に不足カラムを追加する"""
        db = tmp_path / "legacy.db"
        _make_legacy_db(db)
        conn = sqlite3.connect(str(db))
        assert "tokens_in" not in _columns(conn)

        ensure_schema(conn)

        columns = _columns(conn)
        for column in _NEW_COLUMNS:
            assert column in columns

    def test_keeps_existing_rows_with_null_usage(self, tmp_path: Path) -> None:
        """マイグレーションで既存行は保持され、新カラムは NULL になる"""
        db = tmp_path / "legacy.db"
        _make_legacy_db(db, with_row=True)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        ensure_schema(conn)

        row = conn.execute("SELECT * FROM summaries WHERE id = 'old-id'").fetchone()
        assert row is not None
        assert row["summary"] == "旧要約"
        assert row["tokens_in"] is None
        assert row["tokens_out"] is None
        assert row["latency_ms"] is None

    def test_is_idempotent(self, tmp_path: Path) -> None:
        """複数回呼んでも失敗せず、カラムが重複しない"""
        conn = sqlite3.connect(str(tmp_path / "new.db"))

        ensure_schema(conn)
        ensure_schema(conn)
        ensure_schema(conn)

        columns = _columns(conn)
        assert len(columns) == len(set(columns))
