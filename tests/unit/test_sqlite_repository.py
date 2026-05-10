"""SummaryReader のユニットテスト"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pdfsum.errors import PdfsumError
from pdfsum.repositories.sqlite import SummaryReader

_INSERT = "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?)"


def _insert(
    db_path: Path,
    *,
    id: str,
    pdf_path: str,
    pdf_hash: str = "abc123",
    page_count: int = 0,
    summary: str = "テスト要約",
    length: str = "standard",
    model: str = "test-model",
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        _INSERT,
        (id, pdf_path, pdf_hash, page_count, summary, length, model, created_at),
    )
    conn.commit()
    conn.close()


class TestSummaryReader:
    def test_list_all_returns_in_descending_order(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="id1", pdf_path="/a.pdf", created_at="2026-01-01T00:00:00+00:00")
        _insert(db, id="id2", pdf_path="/b.pdf", created_at="2026-02-01T00:00:00+00:00")

        results = reader.list_all()

        assert len(results) == 2
        assert results[0].id == "id2"
        assert results[1].id == "id1"

    def test_list_all_returns_empty_when_no_data(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        assert reader.list_all() == []

    def test_get_returns_none_for_unknown_id(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        assert reader.get("nonexistent-id") is None

    def test_get_returns_summary_for_known_id(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="id1", pdf_path="/a.pdf", summary="要約テキスト", length="short", model="m1")

        result = reader.get("id1")

        assert result is not None
        assert result.id == "id1"
        assert result.summary_text == "要約テキスト"
        assert result.summary_length == "short"
        assert result.model_name == "m1"
        assert result.file_name == "a.pdf"
        assert result.page_count == 0

    def test_get_by_prefix_single_match(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="abcd1234-0000-0000-0000-000000000001", pdf_path="/a.pdf")

        result = reader.get_by_prefix("abcd1234")

        assert result.id == "abcd1234-0000-0000-0000-000000000001"

    def test_get_by_prefix_multiple_match_raises(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="abcd1234-0000-0000-0000-000000000001", pdf_path="/a.pdf", pdf_hash="h1")
        _insert(db, id="abcd1234-0000-0000-0000-000000000002", pdf_path="/b.pdf", pdf_hash="h2")

        with pytest.raises(PdfsumError):
            reader.get_by_prefix("abcd1234")

    def test_get_by_prefix_no_match_raises(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        with pytest.raises(PdfsumError):
            reader.get_by_prefix("xxxxxxxx")

    def test_delete_returns_true_when_deleted(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="id1", pdf_path="/a.pdf")

        result = reader.delete("id1")

        assert result is True
        assert reader.get("id1") is None

    def test_delete_returns_false_when_missing(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        assert reader.delete("nonexistent-id") is False

    def test_resolve_and_delete(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="abcd1234-0000-0000-0000-000000000001", pdf_path="/a.pdf")

        reader.resolve_and_delete("abcd1234")

        assert reader.get("abcd1234-0000-0000-0000-000000000001") is None

    def test_resolve_and_delete_raises_when_no_match(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        with pytest.raises(PdfsumError):
            reader.resolve_and_delete("xxxxxxxx")

    def test_resolve_and_delete_raises_when_delete_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        _insert(db, id="abcd1234-0000-0000-0000-000000000001", pdf_path="/a.pdf")
        monkeypatch.setattr(reader, "delete", lambda _: False)

        with pytest.raises(PdfsumError):
            reader.resolve_and_delete("abcd1234")

    def test_latest_for_path_returns_newest(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        abs_path = str((tmp_path / "doc.pdf").resolve())
        _insert(db, id="id1", pdf_path=abs_path, created_at="2026-01-01T00:00:00+00:00")
        _insert(db, id="id2", pdf_path=abs_path, created_at="2026-02-01T00:00:00+00:00")

        result = reader.latest_for_path(abs_path)

        assert result.id == "id2"

    def test_latest_for_path_raises_when_missing(self, tmp_path: Path) -> None:
        reader = SummaryReader(tmp_path / "test.db")
        with pytest.raises(PdfsumError):
            reader.latest_for_path("/nonexistent/path.pdf")

    def test_latest_for_path_resolves_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        abs_path = str((tmp_path / "doc.pdf").resolve())
        _insert(db, id="id1", pdf_path=abs_path)

        monkeypatch.chdir(tmp_path)
        result = reader.latest_for_path("doc.pdf")

        assert result.id == "id1"
        assert result.pdf_path == abs_path

    def test_latest_for_path_ignores_other_paths(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        reader = SummaryReader(db)
        target_path = str((tmp_path / "target.pdf").resolve())
        other_path = str((tmp_path / "other.pdf").resolve())
        _insert(db, id="id1", pdf_path=target_path, created_at="2026-01-01T00:00:00+00:00")
        _insert(db, id="id2", pdf_path=other_path, created_at="2026-02-01T00:00:00+00:00")

        result = reader.latest_for_path(target_path)

        assert result.id == "id1"

    def test_init_creates_nested_parent_directory(self, tmp_path: Path) -> None:
        nested_db = tmp_path / "a" / "b" / "c" / "test.db"
        SummaryReader(nested_db)
        assert nested_db.exists()
