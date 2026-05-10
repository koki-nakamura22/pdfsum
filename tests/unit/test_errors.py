"""pdfsum.errors のユニットテスト"""

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
        # ImportError が発生しなければパス (公開 I/F 維持確認)
        from pdfsum import (  # noqa: F401
            ConfigError,
            ExtractionError,
            PdfsumError,
            SummarizationError,
        )


class TestFormatDigestkitError:
    """format_digestkit_error の各分岐を検証."""

    def test_configuration_error_includes_setup_message(self) -> None:
        result = format_digestkit_error(DkConfigurationError("setup failed"))
        assert "設定または digestkit の組み立てに失敗しました" in result
        assert "setup failed" in result

    def test_pdfsum_config_error_uses_same_branch_as_dk_configuration_error(self) -> None:
        result = format_digestkit_error(ConfigError("pdfsum config error"))
        assert "設定または digestkit の組み立てに失敗しました" in result
        assert "pdfsum config error" in result

    def test_pdfsum_summarization_error_includes_summary_message(self) -> None:
        result = format_digestkit_error(SummarizationError("summary failed"))
        assert "要約に失敗しました" in result
        assert "summary failed" in result

    def test_digestkit_summarization_error_includes_summary_message(self) -> None:
        result = format_digestkit_error(DkSummarizationError("dk summary failed"))
        assert "要約に失敗しました" in result
        assert "dk summary failed" in result

    def test_pdfsum_extraction_error_includes_extraction_message(self) -> None:
        result = format_digestkit_error(ExtractionError("extraction failed"))
        assert "PDF テキスト抽出に失敗しました" in result
        assert "extraction failed" in result

    def test_sink_error_includes_db_write_message(self) -> None:
        result = format_digestkit_error(DkSinkError("sink failed"))
        assert "DB への書き込みに失敗しました" in result
        assert "sink failed" in result

    def test_unknown_digestkit_error_includes_type_name(self) -> None:
        # _UnknownDkError は特定の digestkit サブクラスにマッチしない汎用スタブ
        result = format_digestkit_error(_UnknownDkError("unknown error"))
        assert "digestkit 処理失敗" in result
        assert "_UnknownDkError" in result
        assert "unknown error" in result

    def test_unrelated_exception_shows_unexpected_failure(self) -> None:
        result = format_digestkit_error(ValueError("unrelated"))
        assert "予期しない失敗" in result
        assert "ValueError" in result
        assert "unrelated" in result

    def test_generic_pdfsum_error_uses_simple_format(self) -> None:
        result = format_digestkit_error(PdfsumError("generic pdfsum error"))
        assert result == "エラー: generic pdfsum error"

    def test_empty_message_is_handled(self) -> None:
        result = format_digestkit_error(DkSinkError(""))
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
