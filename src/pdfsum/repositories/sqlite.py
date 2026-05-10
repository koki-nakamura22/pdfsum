"""summaries テーブルの読み出し/削除. 書き込みは PdfsumSink (digestkit Sink) 担当."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from pdfsum.errors import PdfsumError
from pdfsum.models.summary import Summary

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS summaries ("
    "id TEXT PRIMARY KEY, pdf_path TEXT, pdf_hash TEXT, page_count INTEGER, "
    "summary TEXT, length TEXT, model TEXT, created_at TEXT)"
)


def _row_to_summary(row: sqlite3.Row) -> Summary:
    pdf_path = str(row["pdf_path"])
    return Summary(
        id=str(row["id"]),
        pdf_path=pdf_path,
        pdf_hash=str(row["pdf_hash"]),
        file_name=Path(pdf_path).name,
        page_count=int(row["page_count"]) if row["page_count"] is not None else 0,
        summary_text=str(row["summary"]),
        summary_length=str(row["length"]),
        model_name=str(row["model"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


class SummaryReader:
    """digestkit PdfsumSink が書き込む summaries テーブルの読み出し/削除専用ビュー."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def list_all(self) -> list[Summary]:
        rows = self._conn.execute(
            "SELECT * FROM summaries ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_summary(r) for r in rows]

    def get(self, summary_id: str) -> Summary | None:
        row = self._conn.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        ).fetchone()
        return _row_to_summary(row) if row else None

    def get_by_prefix(self, id_prefix: str) -> Summary:
        rows = self._conn.execute(
            "SELECT * FROM summaries WHERE id LIKE ?", (f"{id_prefix}%",)
        ).fetchall()
        if not rows:
            raise PdfsumError(f"要約が見つかりません (ID: {id_prefix})")
        if len(rows) > 1:
            raise PdfsumError(
                f"複数の要約が一致しました (ID: {id_prefix}). 完全な ID を指定してください."
            )
        return _row_to_summary(rows[0])

    def delete(self, summary_id: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM summaries WHERE id = ?", (summary_id,)
            )
        return cur.rowcount > 0

    def resolve_and_delete(self, prefix: str) -> None:
        target = self.get_by_prefix(prefix)
        deleted = self.delete(target.id)
        if not deleted:
            raise PdfsumError(f"削除に失敗しました (ID: {target.id})")

    def latest_for_path(self, pdf_path: Path | str) -> Summary:
        row = self._conn.execute(
            "SELECT * FROM summaries WHERE pdf_path = ? ORDER BY created_at DESC LIMIT 1",
            (str(Path(pdf_path).resolve()),),
        ).fetchone()
        if not row:
            raise PdfsumError(f"要約が保存されていません (path: {pdf_path})")
        return _row_to_summary(row)
