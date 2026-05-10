"""PdfsumSink のユニットテスト"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from digestkit.sinks import SinkError
from digestkit.types import Digest, Item

from pdfsum.digest.sink import PdfsumSink


def _fetch_rows(db_path: Path) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM summaries")
        return [dict(row) for row in cursor.fetchall()]


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"dummy pdf content")
    return p


@pytest.fixture
def sample_digest() -> Digest:
    return Digest(
        summary="テスト要約",
        tokens_in=10,
        tokens_out=20,
        latency_ms=500,
        model="test-model",
    )


class TestPdfsumSinkInit:
    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """存在しない親ディレクトリを自動作成する"""
        db_path = tmp_path / "nested" / "sub" / "db.sqlite"

        PdfsumSink(db_path, length="standard")

        assert db_path.parent.exists()
        assert db_path.parent.is_dir()

    def test_creates_summaries_table(self, tmp_path: Path) -> None:
        """summaries テーブルを作成する"""
        db_path = tmp_path / "db.sqlite"

        PdfsumSink(db_path, length="standard")

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'"
            )
            assert cursor.fetchone() is not None


class TestPdfsumSinkWrite:
    def test_write_inserts_row_with_uuid_id(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """write() が summaries テーブルに1行挿入し、id が UUID v4 形式である"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        assert len(rows) == 1
        row_id = str(rows[0]["id"])
        parsed = uuid.UUID(row_id, version=4)
        assert str(parsed) == row_id

    def test_write_computes_sha256_from_payload(
        self, tmp_path: Path, sample_digest: Digest
    ) -> None:
        """pdf_hash がファイル内容の SHA-256 hexdigest であることを確認する"""
        content = b"specific pdf bytes for hash check"
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(content)
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf), payload=pdf)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["pdf_hash"] == hashlib.sha256(content).hexdigest()

    def test_pdf_hash_matches_known_value_for_fixed_content(
        self, tmp_path: Path, sample_digest: Digest
    ) -> None:
        """固定バイト列 b'hello' に対して SHA-256 の既知値と一致する"""
        content = b"hello"
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(content)
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf), payload=pdf)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["pdf_hash"] == expected

    def test_length_field_uses_constructor_arg(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """length フィールドがコンストラクタ引数の値で保存される"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="detailed")
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["length"] == "detailed"

    def test_created_at_is_utc_iso8601(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """created_at が UTC オフセット付き ISO 8601 文字列である"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        created_at = str(rows[0]["created_at"])
        dt = datetime.fromisoformat(created_at)
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(0)

    def test_multiple_writes_have_distinct_ids(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """複数回 write しても id (UUID v4) が毎回異なる"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item1 = Item(id=str(pdf_file), payload=pdf_file)
        pdf2 = tmp_path / "doc2.pdf"
        pdf2.write_bytes(b"another pdf content")
        item2 = Item(id=str(pdf2), payload=pdf2)

        sink.write(sample_digest, item1)
        sink.write(sample_digest, item2)

        rows = _fetch_rows(db_path)
        assert len(rows) == 2
        assert rows[0]["id"] != rows[1]["id"]

    def test_pdf_path_field_stores_item_id(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """pdf_path フィールドに Item.id の値が保存される"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(sample_digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["pdf_path"] == str(pdf_file)

    def test_summary_field_stores_digest_summary(
        self, tmp_path: Path, pdf_file: Path
    ) -> None:
        """summary フィールドに Digest.summary の値が保存される"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        digest = Digest(
            summary="特定の要約テキスト", tokens_in=1, tokens_out=1, latency_ms=100, model="m"
        )
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["summary"] == "特定の要約テキスト"

    def test_model_field_stores_digest_model(
        self, tmp_path: Path, pdf_file: Path
    ) -> None:
        """model フィールドに Digest.model の値が保存される"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        digest = Digest(
            summary="s", tokens_in=1, tokens_out=1, latency_ms=100, model="gpt-4o"
        )
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(digest, item)

        rows = _fetch_rows(db_path)
        assert rows[0]["model"] == "gpt-4o"

    def test_str_db_path_is_accepted(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest
    ) -> None:
        """db_path に文字列を渡しても正常に動作する"""
        db_path = str(tmp_path / "db.sqlite")
        sink = PdfsumSink(db_path, length="standard")
        item = Item(id=str(pdf_file), payload=pdf_file)

        sink.write(sample_digest, item)

        rows = _fetch_rows(Path(db_path))
        assert len(rows) == 1

    def test_raises_sink_error_on_sqlite_failure(
        self, tmp_path: Path, pdf_file: Path, sample_digest: Digest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """sqlite3.Error 発生時に SinkError を raise する"""
        db_path = tmp_path / "db.sqlite"
        sink = PdfsumSink(db_path, length="standard")
        # 閉じた接続を差し込んで sqlite3.ProgrammingError を誘発する
        closed_conn = sqlite3.connect(":memory:")
        closed_conn.close()
        monkeypatch.setattr(sink, "_conn", closed_conn)
        item = Item(id=str(pdf_file), payload=pdf_file)

        with pytest.raises(SinkError):
            sink.write(sample_digest, item)
