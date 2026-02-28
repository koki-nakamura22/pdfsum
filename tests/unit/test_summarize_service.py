"""SummarizeService のユニットテスト"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from pdfsum.engines.base import SummarizerEngine
from pdfsum.extractors.pdf_extractor import PDFExtractor
from pdfsum.models.summary import (
    ExtractedDocument,
    ExtractedPage,
    PdfsumError,
    Summary,
)
from pdfsum.repositories.base import SummaryRepository
from pdfsum.services.summarize_service import SummarizeService


def _make_mock_extractor() -> MagicMock:
    """モックPDFExtractorを生成する"""
    extractor = MagicMock(spec=PDFExtractor)
    extractor.extract.return_value = ExtractedDocument(
        file_name="doc.pdf",
        pdf_path="/path/to/doc.pdf",
        pdf_hash="abc123hash",
        page_count=5,
        pages=[
            ExtractedPage(page_number=i, text=f"ページ{i}のテキスト")
            for i in range(1, 6)
        ],
        total_text="テスト用テキスト",
    )
    return extractor


def _make_mock_engine() -> MagicMock:
    """モックSummarizerEngineを生成する"""
    engine = MagicMock(spec=SummarizerEngine)
    engine.summarize.return_value = "要約テキスト"
    engine.get_model_name.return_value = "test-model"
    engine.get_max_input_tokens.return_value = 100_000
    return engine


def _make_mock_repository() -> MagicMock:
    """モックSummaryRepositoryを生成する"""
    repo = MagicMock(spec=SummaryRepository)
    repo.find_by_hash.return_value = None
    repo.find_all.return_value = []
    repo.find_by_id.return_value = None
    repo.find_by_id_prefix.return_value = []
    repo.delete.return_value = True
    return repo


def _make_summary(summary_id: str = "test-uuid") -> Summary:
    """テスト用Summaryオブジェクトを生成する"""
    return Summary(
        id=summary_id,
        pdf_path="/path/to/doc.pdf",
        pdf_hash="abc123hash",
        file_name="doc.pdf",
        page_count=5,
        summary_text="キャッシュ済み要約",
        summary_length="standard",
        model_name="test-model",
        created_at=datetime(2026, 2, 28, 10, 30, 0),
    )


class TestSummarizeServiceSummarize:
    """SummarizeService.summarize() のテスト"""

    def test_summarize_returns_cached_summary_when_exists(self) -> None:
        """キャッシュヒット時にキャッシュ済み要約を返す"""
        extractor = _make_mock_extractor()
        engine = _make_mock_engine()
        repo = _make_mock_repository()
        cached = _make_summary()
        repo.find_by_hash.return_value = cached

        service = SummarizeService(extractor, engine, repo)
        result = service.summarize("/path/to/doc.pdf", "standard")

        assert result == cached
        engine.summarize.assert_not_called()
        repo.save.assert_not_called()

    def test_summarize_generates_and_saves_on_cache_miss(self) -> None:
        """キャッシュミス時に要約を生成して保存する"""
        extractor = _make_mock_extractor()
        engine = _make_mock_engine()
        repo = _make_mock_repository()

        service = SummarizeService(extractor, engine, repo)
        result = service.summarize("/path/to/doc.pdf", "standard")

        assert result.summary_text == "要約テキスト"
        assert result.pdf_hash == "abc123hash"
        assert result.model_name == "test-model"
        assert result.summary_length == "standard"
        repo.save.assert_called_once()

    def test_summarize_calls_extractor_with_pdf_path(self) -> None:
        """PDFExtractorにパスを渡して呼び出す"""
        extractor = _make_mock_extractor()
        engine = _make_mock_engine()
        repo = _make_mock_repository()

        service = SummarizeService(extractor, engine, repo)
        service.summarize("/path/to/doc.pdf", "standard")

        extractor.extract.assert_called_once_with("/path/to/doc.pdf")

    def test_summarize_checks_cache_with_hash_and_length(self) -> None:
        """ハッシュと要約長でキャッシュを確認する"""
        extractor = _make_mock_extractor()
        engine = _make_mock_engine()
        repo = _make_mock_repository()

        service = SummarizeService(extractor, engine, repo)
        service.summarize("/path/to/doc.pdf", "detailed")

        repo.find_by_hash.assert_called_once_with("abc123hash", "detailed")


class TestSummarizeServiceList:
    """SummarizeService.list_summaries() のテスト"""

    def test_list_summaries_calls_find_all(self) -> None:
        """find_allを呼び出して一覧を返す"""
        repo = _make_mock_repository()
        summaries = [_make_summary("id-1"), _make_summary("id-2")]
        repo.find_all.return_value = summaries

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)
        result = service.list_summaries()

        assert result == summaries
        repo.find_all.assert_called_once()


class TestSummarizeServiceGetSummary:
    """SummarizeService.get_summary() のテスト"""

    def test_get_summary_calls_find_by_id(self) -> None:
        """find_by_idを呼び出して要約を返す"""
        repo = _make_mock_repository()
        summary = _make_summary()
        repo.find_by_id.return_value = summary

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)
        result = service.get_summary("test-uuid")

        assert result == summary
        repo.find_by_id.assert_called_once_with("test-uuid")


class TestSummarizeServiceGetByPrefix:
    """SummarizeService.get_summary_by_prefix() のテスト"""

    def test_get_summary_by_prefix_returns_single_match(self) -> None:
        """1件一致時に要約を返す"""
        repo = _make_mock_repository()
        summary = _make_summary()
        repo.find_by_id_prefix.return_value = [summary]

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)
        result = service.get_summary_by_prefix("a1b2c3d4")

        assert result == summary

    def test_get_summary_by_prefix_raises_error_when_no_match(self) -> None:
        """0件一致でPdfsumErrorを送出する"""
        repo = _make_mock_repository()
        repo.find_by_id_prefix.return_value = []

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)

        with pytest.raises(PdfsumError, match="要約が見つかりません"):
            service.get_summary_by_prefix("xxxxxxxx")

    def test_get_summary_by_prefix_raises_error_when_multiple_matches(
        self,
    ) -> None:
        """複数一致でPdfsumErrorを送出する"""
        repo = _make_mock_repository()
        repo.find_by_id_prefix.return_value = [
            _make_summary("id-1"),
            _make_summary("id-2"),
        ]

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)

        with pytest.raises(PdfsumError, match="複数の要約が一致しました"):
            service.get_summary_by_prefix("a1b2c3d4")


class TestSummarizeServiceDelete:
    """SummarizeService.delete_summary() / resolve_and_delete() のテスト"""

    def test_delete_summary_calls_repository_delete(self) -> None:
        """repository.deleteを呼び出す"""
        repo = _make_mock_repository()

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)
        result = service.delete_summary("test-uuid")

        assert result is True
        repo.delete.assert_called_once_with("test-uuid")

    def test_resolve_and_delete_resolves_prefix_then_deletes(self) -> None:
        """短縮IDを解決してからdeleteを呼び出す"""
        repo = _make_mock_repository()
        summary = _make_summary("full-uuid-here")
        repo.find_by_id_prefix.return_value = [summary]

        service = SummarizeService(_make_mock_extractor(), _make_mock_engine(), repo)
        result = service.resolve_and_delete("full-uui")

        assert result is True
        repo.delete.assert_called_once_with("full-uuid-here")
