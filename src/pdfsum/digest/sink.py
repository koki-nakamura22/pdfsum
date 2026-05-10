"""pdfsum 既存スキーマへ書き込む digestkit Sink 実装."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from digestkit.sinks import SinkError
from digestkit.types import Digest, Item

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS summaries ("
    "id TEXT PRIMARY KEY, pdf_path TEXT, pdf_hash TEXT, "
    "summary TEXT, length TEXT, model TEXT, created_at TEXT)"
)
_INSERT = "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, ?, ?)"


class PdfsumSink:
    """digestkit Sink プロトコルを実装し pdfsum 既存スキーマへ書き込む.

    Item.id (= PDF ファイルパス文字列) から Path を復元し SHA-256 を計算、
    UUID v4 + length (CLI 引数) と組み合わせて summaries テーブルへ INSERT する。
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
            pdf_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            with self._conn:
                self._conn.execute(
                    _INSERT,
                    (
                        str(uuid.uuid4()),
                        str(pdf_path),
                        pdf_hash,
                        digest.summary,
                        self._length,
                        digest.model,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            raise SinkError(str(e)) from e
