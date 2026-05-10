"""pdfsum.errors のユニットテスト"""

import pytest
from digestkit import ConfigurationError as DkConfigurationError
from digestkit import DigestkitError as DkDigestkitError
from digestkit.sinks import SinkError as DkSinkError
from digestkit.summarizers import SummarizationError as DkSummarizationError

from pdfsum.errors import (
    ConfigError,
    ExtractionError,
    PdfsumError,
    SummarizationError,
    exit_code_for,
    format_digestkit_error,
)


class _UnknownDkError(DkDigestkitError):
    """format_digestkit_error の汎用 DigestkitError 分岐検証用スタブ."""


class TestPdfsumErrorHierarchy:
    """公開 API の継承関係 (★公開 I/F 維持)."""

    def test_config_error_is_pdfsum_error(self) -> None:
        assert issubclass(ConfigError, PdfsumError)

    def test_extraction_error_is_pdfsum_error(self) -> None:
        assert issubclass(ExtractionError, PdfsumError)

    def test_summarization_error_is_pdfsum_error(self) -> None:
        assert issubclass(SummarizationError, PdfsumError)

    def test_pdfsum_error_is_exception(self) -> None:
        assert issubclass(PdfsumError, Exception)

    def test_config_error_is_instantiable(self) -> None:
        exc = ConfigError("設定エラー")
        assert str(exc) == "設定エラー"

    def test_extraction_error_is_instantiable(self) -> None:
        exc = ExtractionError("抽出エラー")
        assert str(exc) == "抽出エラー"

    def test_summarization_error_is_instantiable(self) -> None:
        exc = SummarizationError("要約エラー")
        assert str(exc) == "要約エラー"


class TestPublicImportPath:
    """from pdfsum import <例外> が成立 (★公開 I/F 維持)."""

    def test_import_from_pdfsum_root(self) -> None:
        from pdfsum import (  # noqa: F401
            ConfigError,
            ExtractionError,
            PdfsumError,
            SummarizationError,
        )


class TestFormatDigestkitError:
    """format_digestkit_error の各分岐を検証."""

    def test_configuration_error_includes_setup_message(self) -> None:
        # Arrange
        exc = DkConfigurationError("setup failed")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "設定または digestkit の組み立てに失敗しました" in result
        assert "setup failed" in result

    def test_pdfsum_config_error_uses_same_branch_as_dk_configuration_error(self) -> None:
        exc = ConfigError("pdfsum config error")
        result = format_digestkit_error(exc)
        assert "設定または digestkit の組み立てに失敗しました" in result
        assert "pdfsum config error" in result

    def test_pdfsum_summarization_error_includes_summary_message(self) -> None:
        # Arrange
        exc = SummarizationError("summary failed")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "要約に失敗しました" in result
        assert "summary failed" in result

    def test_digestkit_summarization_error_includes_summary_message(self) -> None:
        # Arrange
        exc = DkSummarizationError("dk summary failed")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "要約に失敗しました" in result
        assert "dk summary failed" in result

    def test_pdfsum_extraction_error_includes_extraction_message(self) -> None:
        # Arrange
        exc = ExtractionError("extraction failed")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "PDF テキスト抽出に失敗しました" in result
        assert "extraction failed" in result

    def test_sink_error_includes_db_write_message(self) -> None:
        # Arrange
        exc = DkSinkError("sink failed")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "DB への書き込みに失敗しました" in result
        assert "sink failed" in result

    def test_unknown_digestkit_error_includes_type_name(self) -> None:
        # Arrange: use a custom subclass not covered by specific branches
        exc = _UnknownDkError("unknown error")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "digestkit 処理失敗" in result
        assert "_UnknownDkError" in result
        assert "unknown error" in result

    def test_unrelated_exception_shows_unexpected_failure(self) -> None:
        # Arrange
        exc = ValueError("unrelated")
        # Act
        result = format_digestkit_error(exc)
        # Assert
        assert "予期しない失敗" in result
        assert "ValueError" in result
        assert "unrelated" in result

    def test_generic_pdfsum_error_uses_simple_format(self) -> None:
        exc = PdfsumError("generic pdfsum error")
        result = format_digestkit_error(exc)
        assert result == "エラー: generic pdfsum error"

    def test_empty_message_is_handled(self) -> None:
        exc = DkSinkError("")
        result = format_digestkit_error(exc)
        assert "DB への書き込みに失敗しました" in result


class TestExitCodeFor:
    """exit_code_for の各分岐を検証."""

    def test_pdfsum_error_returns_one(self) -> None:
        assert exit_code_for(PdfsumError("error")) == 1

    def test_extraction_error_returns_one(self) -> None:
        assert exit_code_for(ExtractionError("error")) == 1

    def test_summarization_error_returns_one(self) -> None:
        assert exit_code_for(SummarizationError("error")) == 1

    def test_config_error_returns_two(self) -> None:
        assert exit_code_for(ConfigError("error")) == 2

    def test_digestkit_configuration_error_returns_two(self) -> None:
        assert exit_code_for(DkConfigurationError("error")) == 2

    def test_digestkit_summarization_error_returns_one(self) -> None:
        assert exit_code_for(DkSummarizationError("error")) == 1

    def test_sink_error_returns_one(self) -> None:
        assert exit_code_for(DkSinkError("error")) == 1

    def test_unknown_digestkit_error_returns_one(self) -> None:
        assert exit_code_for(_UnknownDkError("error")) == 1

    def test_unrelated_exception_returns_one(self) -> None:
        assert exit_code_for(ValueError("error")) == 1

    def test_runtime_error_returns_one(self) -> None:
        assert exit_code_for(RuntimeError("error")) == 1
