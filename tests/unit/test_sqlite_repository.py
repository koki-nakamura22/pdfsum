"""SQLiteSummaryRepository のユニットテスト"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from pdfsum.models.summary import Summary
from pdfsum.repositories.sqlite import SQLiteSummaryRepository


def _make_summary(
    summary_id: str = "a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6",
    pdf_hash: str = "abc123",
    summary_length: str = "standard",
) -> Summary:
    """テスト用のSummaryオブジェクトを生成する"""
    return Summary(
        id=summary_id,
        pdf_path="/path/to/doc.pdf",
        pdf_hash=pdf_hash,
        file_name="doc.pdf",
        page_count=10,
        summary_text="テスト要約テキスト",
        summary_length=summary_length,
        model_name="test-model",
        created_at=datetime(2026, 2, 28, 10, 30, 0),
    )


class TestSQLiteSummaryRepository:
    """SQLiteSummaryRepository のテスト"""

    def setup_method(self) -> None:
        self.repo = SQLiteSummaryRepository(":memory:")

    def test_save_and_find_by_id(self) -> None:
        """保存した要約をIDで取得できる"""
        summary = _make_summary()
        self.repo.save(summary)

        result = self.repo.find_by_id(summary.id)

        assert result is not None
        assert result.id == summary.id
        assert result.pdf_path == summary.pdf_path
        assert result.pdf_hash == summary.pdf_hash
        assert result.file_name == summary.file_name
        assert result.page_count == summary.page_count
        assert result.summary_text == summary.summary_text
        assert result.summary_length == summary.summary_length
        assert result.model_name == summary.model_name
        assert result.created_at == summary.created_at

    def test_find_by_id_returns_none_for_unknown_id(self) -> None:
        """存在しないIDの場合Noneを返す"""
        result = self.repo.find_by_id("nonexistent-id")
        assert result is None

    def test_find_by_id_prefix(self) -> None:
        """IDプレフィックスで前方一致検索できる"""
        summary = _make_summary(summary_id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6")
        self.repo.save(summary)

        results = self.repo.find_by_id_prefix("a1b2c3d4")

        assert len(results) == 1
        assert results[0].id == summary.id

    def test_find_by_id_prefix_returns_empty_for_no_match(self) -> None:
        """一致しないプレフィックスの場合空リストを返す"""
        results = self.repo.find_by_id_prefix("xxxxxxxx")
        assert results == []

    def test_find_by_hash(self) -> None:
        """PDFハッシュと要約長でキャッシュ検索できる"""
        summary = _make_summary(pdf_hash="hash123", summary_length="standard")
        self.repo.save(summary)

        result = self.repo.find_by_hash("hash123", "standard")

        assert result is not None
        assert result.pdf_hash == "hash123"
        assert result.summary_length == "standard"

    def test_find_by_hash_returns_none_for_different_length(self) -> None:
        """同一ハッシュでも異なる要約長では見つからない"""
        summary = _make_summary(pdf_hash="hash123", summary_length="standard")
        self.repo.save(summary)

        result = self.repo.find_by_hash("hash123", "short")
        assert result is None

    def test_find_all_returns_descending_order(self) -> None:
        """全件取得はcreated_at降順で返す"""
        summary1 = _make_summary(
            summary_id="id-1",
            pdf_hash="hash1",
        )
        summary1.created_at = datetime(2026, 1, 1, 0, 0, 0)

        summary2 = _make_summary(
            summary_id="id-2",
            pdf_hash="hash2",
        )
        summary2.created_at = datetime(2026, 2, 1, 0, 0, 0)

        self.repo.save(summary1)
        self.repo.save(summary2)

        results = self.repo.find_all()

        assert len(results) == 2
        assert results[0].id == "id-2"  # 新しい方が先
        assert results[1].id == "id-1"

    def test_delete_returns_true_on_success(self) -> None:
        """存在する要約の削除はTrueを返す"""
        summary = _make_summary()
        self.repo.save(summary)

        result = self.repo.delete(summary.id)

        assert result is True
        assert self.repo.find_by_id(summary.id) is None

    def test_delete_returns_false_for_unknown_id(self) -> None:
        """存在しないIDの削除はFalseを返す"""
        result = self.repo.delete("nonexistent-id")
        assert result is False

    def test_find_all_returns_empty_list_when_no_data(self) -> None:
        """データがない場合空リストを返す"""
        results = self.repo.find_all()
        assert results == []

    def test_find_by_id_prefix_multiple_matches(self) -> None:
        """同じプレフィックスで複数一致する場合のテスト"""
        summary1 = _make_summary(
            summary_id="a1b2c3d4-0000-0000-0000-000000000001",
            pdf_hash="hash1",
        )
        summary2 = _make_summary(
            summary_id="a1b2c3d4-0000-0000-0000-000000000002",
            pdf_hash="hash2",
        )
        self.repo.save(summary1)
        self.repo.save(summary2)

        results = self.repo.find_by_id_prefix("a1b2c3d4")

        assert len(results) == 2

    def test_close_closes_connection(self) -> None:
        """close()でDB接続が閉じられる"""
        self.repo.close()
        with pytest.raises(sqlite3.ProgrammingError):
            self.repo.find_all()

    def test_context_manager_returns_self(self) -> None:
        """__enter__でself が返される"""
        repo = SQLiteSummaryRepository(":memory:")
        with repo as r:
            assert r is repo

    def test_context_manager_closes_on_exit(self) -> None:
        """コンテキストマネージャ終了時にDB接続が閉じられる"""
        repo = SQLiteSummaryRepository(":memory:")
        with repo:
            repo.save(_make_summary())
        with pytest.raises(sqlite3.ProgrammingError):
            repo.find_all()

    def test_init_with_file_path_creates_directory(
        self, tmp_path: Path
    ) -> None:
        """実ファイルパスで初期化時にディレクトリが作成される"""
        db_path = tmp_path / "nested" / "dir" / "test.db"
        repo = SQLiteSummaryRepository(str(db_path))

        assert db_path.parent.exists()
        assert db_path.exists()
        repo.close()

    def test_init_with_file_path_sets_permissions(
        self, tmp_path: Path
    ) -> None:
        """実ファイルパスで初期化時にファイル権限が0o600に設定される"""
        db_path = tmp_path / "perm_test.db"
        repo = SQLiteSummaryRepository(str(db_path))

        stat = os.stat(db_path)
        assert stat.st_mode & 0o777 == 0o600
        repo.close()

    @pytest.mark.parametrize("summary_length", ["short", "standard", "detailed"])
    def test_save_accepts_valid_summary_lengths(
        self, summary_length: str
    ) -> None:
        """有効な要約長（short/standard/detailed）が保存できる"""
        summary = _make_summary(
            summary_id=f"id-{summary_length}",
            summary_length=summary_length,
            pdf_hash=f"hash-{summary_length}",
        )
        self.repo.save(summary)

        result = self.repo.find_by_id(f"id-{summary_length}")
        assert result is not None
        assert result.summary_length == summary_length
