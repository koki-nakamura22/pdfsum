"""SummarizeService のユニットテスト"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import digestkit
from pdfsum.config.manager import Config, DatabaseConfig, LLMConfig, SummaryConfig
from pdfsum.errors import ExtractionError, SummarizationError
from pdfsum.models.summary import PdfsumError, Summary
from pdfsum.services.summarize_service import (
    SummarizeService,
    build_digester,
    run_summarize,
)


def _make_summary(summary_id: str = "test-uuid") -> Summary:
    return Summary(
        id=summary_id,
        pdf_path="/path/to/doc.pdf",
        pdf_hash="abc123hash",
        file_name="doc.pdf",
        page_count=0,
        summary_text="要約テキスト",
        summary_length="standard",
        model_name="test-model",
        created_at=datetime(2026, 2, 28, 10, 30, 0),
    )


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    return Config(
        llm=LLMConfig(provider="test-provider", model="test-model"),
        summary=SummaryConfig(chunked=False, extra_instructions=""),
        database=DatabaseConfig(path=str(tmp_path / "test.db")),
    )


class TestSummarizeServicePublicAPI:
    """公開 API のシグネチャ・戻り値が旧版と互換であることを保証."""

    def test_summarize_returns_summary(self, mock_config: Config) -> None:
        expected = _make_summary()
        with patch("pdfsum.services.summarize_service.SummaryReader"), \
             patch("pdfsum.services.summarize_service.run_summarize", return_value=expected):
            service = SummarizeService(mock_config)
            result = service.summarize("/path/to/doc.pdf", "standard")
        assert result is expected

    def test_summarize_accepts_str_path(self, mock_config: Config) -> None:
        with patch("pdfsum.services.summarize_service.SummaryReader"), \
             patch("pdfsum.services.summarize_service.run_summarize", return_value=_make_summary()) as mock_run:
            service = SummarizeService(mock_config)
            service.summarize("/path/to/doc.pdf", "standard")
        mock_run.assert_called_once_with(mock_config, Path("/path/to/doc.pdf"), "standard")

    def test_summarize_accepts_path_obj(self, mock_config: Config) -> None:
        pdf_path = Path("/path/to/doc.pdf")
        with patch("pdfsum.services.summarize_service.SummaryReader"), \
             patch("pdfsum.services.summarize_service.run_summarize", return_value=_make_summary()) as mock_run:
            service = SummarizeService(mock_config)
            service.summarize(pdf_path, "standard")
        mock_run.assert_called_once_with(mock_config, pdf_path, "standard")

    def test_list_summaries_returns_list(self, mock_config: Config) -> None:
        summaries = [_make_summary("id-1"), _make_summary("id-2")]
        mock_reader = MagicMock()
        mock_reader.list_all.return_value = summaries
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.list_summaries()
        assert result == summaries
        mock_reader.list_all.assert_called_once()

    def test_get_summary_returns_none_for_unknown(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.get.return_value = None
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.get_summary("unknown-id")
        assert result is None
        mock_reader.get.assert_called_once_with("unknown-id")

    def test_get_summary_by_prefix_raises_on_multiple(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.get_by_prefix.side_effect = PdfsumError("複数の要約が一致しました")
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            with pytest.raises(PdfsumError, match="複数の要約が一致しました"):
                service.get_summary_by_prefix("abc")

    def test_get_summary_by_prefix_raises_when_no_match(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.get_by_prefix.side_effect = PdfsumError("要約が見つかりません")
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            with pytest.raises(PdfsumError, match="要約が見つかりません"):
                service.get_summary_by_prefix("nonexistent")

    def test_get_summary_returns_summary_when_found(self, mock_config: Config) -> None:
        expected = _make_summary()
        mock_reader = MagicMock()
        mock_reader.get.return_value = expected
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.get_summary("test-uuid")
        assert result is expected
        mock_reader.get.assert_called_once_with("test-uuid")

    def test_get_summary_by_prefix_returns_single_match(self, mock_config: Config) -> None:
        expected = _make_summary()
        mock_reader = MagicMock()
        mock_reader.get_by_prefix.return_value = expected
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.get_summary_by_prefix("test-")
        assert result is expected

    def test_delete_summary_returns_bool(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.delete.return_value = True
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.delete_summary("test-uuid")
        assert result is True
        mock_reader.delete.assert_called_once_with("test-uuid")

    def test_delete_summary_returns_false_when_not_found(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.delete.return_value = False
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.delete_summary("nonexistent-uuid")
        assert result is False

    def test_resolve_and_delete_resolves_prefix_then_deletes(self, mock_config: Config) -> None:
        target = _make_summary("full-uuid-here")
        mock_reader = MagicMock()
        mock_reader.get_by_prefix.return_value = target
        mock_reader.delete.return_value = True
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            result = service.resolve_and_delete("full-uui")
        assert result is True
        mock_reader.get_by_prefix.assert_called_once_with("full-uui")
        mock_reader.delete.assert_called_once_with("full-uuid-here")

    def test_resolve_and_delete_propagates_not_found_error(self, mock_config: Config) -> None:
        mock_reader = MagicMock()
        mock_reader.get_by_prefix.side_effect = PdfsumError("要約が見つかりません")
        with patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            service = SummarizeService(mock_config)
            with pytest.raises(PdfsumError, match="要約が見つかりません"):
                service.resolve_and_delete("xxxxxxxx")


class TestBuildDigester:
    def test_uses_chunked_when_config_chunked(self, mock_config: Config) -> None:
        mock_config.summary.chunked = True
        with patch("pdfsum.services.summarize_service.ChunkedLLMSummarizer") as mock_cls, \
             patch("digestkit.Digester"), \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = {}
            build_digester(mock_config, Path("/tmp/test.pdf"), "standard")
        mock_cls.assert_called_once()

    def test_uses_llm_when_config_not_chunked(self, mock_config: Config) -> None:
        mock_config.summary.chunked = False
        with patch("pdfsum.services.summarize_service.LLMSummarizer") as mock_cls, \
             patch("digestkit.Digester"), \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = {}
            build_digester(mock_config, Path("/tmp/test.pdf"), "standard")
        mock_cls.assert_called_once()

    def test_passes_default_prompts_when_no_extra(self, mock_config: Config) -> None:
        mock_config.summary.extra_instructions = ""
        default_prompts = {"standard": "summarize {text}"}
        with patch("pdfsum.services.summarize_service.LLMSummarizer") as mock_cls, \
             patch("digestkit.Digester"), \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = default_prompts
            build_digester(mock_config, Path("/tmp/test.pdf"), "standard")
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["prompts"] == default_prompts

    def test_appends_extra_instructions_to_prompts(self, mock_config: Config) -> None:
        mock_config.summary.extra_instructions = "日本語で"
        default_prompts = {"standard": "summarize {text}"}
        with patch("pdfsum.services.summarize_service.LLMSummarizer") as mock_cls, \
             patch("digestkit.Digester"), \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = default_prompts
            build_digester(mock_config, Path("/tmp/test.pdf"), "standard")
        call_kwargs = mock_cls.call_args.kwargs
        assert "日本語で" in call_kwargs["prompts"]["standard"]

    def test_passes_default_length(self, mock_config: Config) -> None:
        with patch("pdfsum.services.summarize_service.LLMSummarizer") as mock_cls, \
             patch("digestkit.Digester"), \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = {}
            build_digester(mock_config, Path("/tmp/test.pdf"), "detailed")
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["default_length"] == "detailed"

    def test_uses_content_sha256_dedup_key(self, mock_config: Config) -> None:
        with patch("pdfsum.services.summarize_service.LLMSummarizer") as mock_cls, \
             patch("digestkit.Digester") as mock_digester_cls, \
             patch("pdfsum.services.summarize_service.PdfsumSink"):
            mock_cls.DEFAULT_PROMPTS = {}
            build_digester(mock_config, Path("/tmp/test.pdf"), "standard")
        call_kwargs = mock_digester_cls.call_args.kwargs
        assert call_kwargs["dedup_key"] is digestkit.content_sha256_key


class TestRunSummarize:
    def test_returns_summary_on_success(self, mock_config: Config) -> None:
        expected = _make_summary()
        mock_digester = MagicMock()
        mock_result = MagicMock()
        mock_result.failures = []
        mock_digester.run.return_value = mock_result
        mock_reader = MagicMock()
        mock_reader.latest_for_path.return_value = expected
        pdf_path = Path("/tmp/test.pdf")
        with patch("pdfsum.services.summarize_service.build_digester", return_value=mock_digester), \
             patch("pdfsum.services.summarize_service.SummaryReader", return_value=mock_reader):
            result = run_summarize(mock_config, pdf_path, "standard")
        assert result is expected
        mock_digester.run.assert_called_once_with(limit=1, length="standard")

    def test_raises_summarization_error_on_summarize_failure(
        self, mock_config: Config
    ) -> None:
        from digestkit.summarizers import SummarizationError as DigestkitErr
        mock_digester = MagicMock()
        mock_digester.run.side_effect = DigestkitErr("LLM呼び出し失敗")
        with patch("pdfsum.services.summarize_service.build_digester", return_value=mock_digester), \
             patch("pdfsum.services.summarize_service.SummaryReader"):
            with pytest.raises(SummarizationError, match="LLM呼び出し失敗"):
                run_summarize(mock_config, Path("/tmp/test.pdf"), "standard")

    def test_raises_extraction_error_from_extractor_exception(
        self, mock_config: Config
    ) -> None:
        from digestkit.extractors import ExtractionError as DigestkitExtractionError
        mock_digester = MagicMock()
        mock_digester.run.side_effect = DigestkitExtractionError("PDF corrupt")
        with patch("pdfsum.services.summarize_service.build_digester", return_value=mock_digester), \
             patch("pdfsum.services.summarize_service.SummaryReader"):
            with pytest.raises(ExtractionError, match="PDF corrupt"):
                run_summarize(mock_config, Path("/tmp/test.pdf"), "standard")

    def test_raises_extraction_error_on_extract_stage_failure(
        self, mock_config: Config
    ) -> None:
        mock_digester = MagicMock()
        mock_result = MagicMock()
        failure = MagicMock()
        failure.stage = "extract"
        failure.error = ValueError("PDF読み取り失敗")
        mock_result.failures = [failure]
        mock_digester.run.return_value = mock_result
        with patch("pdfsum.services.summarize_service.build_digester", return_value=mock_digester), \
             patch("pdfsum.services.summarize_service.SummaryReader"):
            with pytest.raises(ExtractionError):
                run_summarize(mock_config, Path("/tmp/test.pdf"), "standard")

    def test_raises_summarization_error_on_summarize_stage_failure(
        self, mock_config: Config
    ) -> None:
        mock_digester = MagicMock()
        mock_result = MagicMock()
        failure = MagicMock()
        failure.stage = "summarize"
        failure.error = RuntimeError("LLM応答エラー")
        mock_result.failures = [failure]
        mock_digester.run.return_value = mock_result
        with patch("pdfsum.services.summarize_service.build_digester", return_value=mock_digester), \
             patch("pdfsum.services.summarize_service.SummaryReader"):
            with pytest.raises(SummarizationError):
                run_summarize(mock_config, Path("/tmp/test.pdf"), "standard")
