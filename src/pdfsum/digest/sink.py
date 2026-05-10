"""pdfsum 既存スキーマへ書き込む digestkit Sink 実装."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pypdf
from digestkit.sinks import SinkError
from digestkit.types import Digest, Item

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS summaries ("
    "id TEXT PRIMARY KEY, pdf_path TEXT, pdf_hash TEXT, page_count INTEGER, "
    "summary TEXT, length TEXT, model TEXT, created_at TEXT)"
)
_INSERT = "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?)"


class PdfsumSink:
    """digestkit Sink プロトコルを実装し pdfsum スキーマへ書き込む.

    Item.id (= PDF ファイルパス文字列) から Path を復元し、SHA-256 と
    page_count (pypdf 経由) を計算、UUID v4 + length (CLI 引数) と組み合わせて
    summaries テーブルへ INSERT する。page_count は外部表示 (`show` の "ページ数")
    で使われる公開フィールドなので、digestkit Digest に乗らない情報を pdfsum
    側でこのタイミングだけ計算する。
    """

    def __init__(self, db_path: Path | str, *, length: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._length = length
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def write(self, digest: Digest, item: Item) -> None:
        try:
            pdf_path = Path(item.id)
            pdf_bytes = pdf_path.read_bytes()
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            page_count = _count_pages(pdf_path)
            with self._conn:
                self._conn.execute(
                    _INSERT,
                    (
                        str(uuid.uuid4()),
                        str(pdf_path),
                        pdf_hash,
                        page_count,
                        digest.summary,
                        self._length,
                        digest.model,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            raise SinkError(str(e)) from e


def _count_pages(pdf_path: Path) -> int:
    """PDF のページ数を pypdf で取得する. 失敗時は 0 を返す (best-effort)."""
    try:
        return len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        return 0
