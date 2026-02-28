"""SQLiteを使用した要約リポジトリ実装"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from pdfsum.models.summary import Summary
from pdfsum.repositories.base import SummaryRepository

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    pdf_path TEXT NOT NULL,
    pdf_hash TEXT NOT NULL,
    file_name TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    summary_length TEXT NOT NULL
        CHECK(summary_length IN ('short', 'standard', 'detailed')),
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_summaries_pdf_hash
ON summaries(pdf_hash, summary_length)
"""


class SQLiteSummaryRepository(SummaryRepository):
    """SQLiteを使用したSummaryRepository実装"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_directory(db_path)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(CREATE_TABLE_SQL)
        self._conn.execute(CREATE_INDEX_SQL)
        self._conn.commit()

    def close(self) -> None:
        """DB接続を閉じる"""
        self._conn.close()

    def __enter__(self) -> "SQLiteSummaryRepository":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def _ensure_directory(self, db_path: str) -> None:
        """DBファイルの親ディレクトリを作成し、権限を設定する"""
        if db_path == ":memory:":
            return
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # ファイルを作成して権限設定
            path.touch()
            os.chmod(path, 0o600)

    def save(self, summary: Summary) -> None:
        """要約を保存する。

        Args:
            summary: 保存する要約オブジェクト
        """
        self._conn.execute(
            """INSERT INTO summaries
               (id, pdf_path, pdf_hash, file_name, page_count,
                summary_text, summary_length, model_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                summary.id,
                summary.pdf_path,
                summary.pdf_hash,
                summary.file_name,
                summary.page_count,
                summary.summary_text,
                summary.summary_length,
                summary.model_name,
                summary.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def find_by_id(self, summary_id: str) -> Summary | None:
        """完全なIDで要約を取得する。

        Args:
            summary_id: UUID v4形式の要約ID

        Returns:
            要約オブジェクト。見つからない場合はNone
        """
        cursor = self._conn.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_summary(row)

    def find_by_id_prefix(self, id_prefix: str) -> list[Summary]:
        """IDの前方一致で要約を検索する。

        Args:
            id_prefix: IDの先頭部分

        Returns:
            一致した要約のリスト
        """
        cursor = self._conn.execute(
            "SELECT * FROM summaries WHERE id LIKE ? || '%'", (id_prefix,)
        )
        return [self._row_to_summary(row) for row in cursor.fetchall()]

    def find_by_hash(self, pdf_hash: str, summary_length: str) -> Summary | None:
        """PDFハッシュと要約長で要約を検索する。

        Args:
            pdf_hash: PDFファイルのSHA-256ハッシュ
            summary_length: 要約の長さ

        Returns:
            要約オブジェクト。見つからない場合はNone
        """
        cursor = self._conn.execute(
            "SELECT * FROM summaries WHERE pdf_hash = ? AND summary_length = ?",
            (pdf_hash, summary_length),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_summary(row)

    def find_all(self) -> list[Summary]:
        """全要約を作成日時の降順で取得する。

        Returns:
            要約のリスト
        """
        cursor = self._conn.execute(
            "SELECT * FROM summaries ORDER BY created_at DESC"
        )
        return [self._row_to_summary(row) for row in cursor.fetchall()]

    def delete(self, summary_id: str) -> bool:
        """要約を削除する。

        Args:
            summary_id: 削除する要約のID

        Returns:
            削除に成功した場合True、見つからない場合False
        """
        cursor = self._conn.execute(
            "DELETE FROM summaries WHERE id = ?", (summary_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def _row_to_summary(self, row: sqlite3.Row) -> Summary:
        """DBの行データをSummaryオブジェクトに変換する"""
        return Summary(
            id=row["id"],
            pdf_path=row["pdf_path"],
            pdf_hash=row["pdf_hash"],
            file_name=row["file_name"],
            page_count=row["page_count"],
            summary_text=row["summary_text"],
            summary_length=row["summary_length"],
            model_name=row["model_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
