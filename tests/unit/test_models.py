"""データモデルとカスタム例外のユニットテスト"""

from datetime import datetime

from pdfsum.models.summary import (
    ConfigError,
    ExtractionError,
    PdfsumError,
    SummarizationError,
    Summary,
)


class TestSummary:
    """Summary データクラスのテスト"""

    def test_create_summary(self) -> None:
        """Summaryが正しく生成される"""
        now = datetime.now()
        summary = Summary(
            id="12345678-1234-1234-1234-123456789abc",
            pdf_path="/path/to/test.pdf",
            pdf_hash="a" * 64,
            file_name="test.pdf",
            page_count=10,
            summary_text="This is a summary.",
            summary_length="standard",
            model_name="gemini-2.5-flash",
            created_at=now,
        )

        assert summary.id == "12345678-1234-1234-1234-123456789abc"
        assert summary.summary_length == "standard"
        assert summary.model_name == "gemini-2.5-flash"
        assert summary.created_at == now


class TestCustomExceptions:
    """カスタム例外クラスのテスト"""

    def test_pdfsumerror_is_base_exception(self) -> None:
        """PdfsumErrorがExceptionを継承している"""
        assert issubclass(PdfsumError, Exception)

    def test_extraction_error_inherits_pdfsumerror(self) -> None:
        """ExtractionErrorがPdfsumErrorを継承している"""
        assert issubclass(ExtractionError, PdfsumError)

    def test_summarization_error_inherits_pdfsumerror(self) -> None:
        """SummarizationErrorがPdfsumErrorを継承している"""
        assert issubclass(SummarizationError, PdfsumError)

    def test_config_error_inherits_pdfsumerror(self) -> None:
        """ConfigErrorがPdfsumErrorを継承している"""
        assert issubclass(ConfigError, PdfsumError)

    def test_extraction_error_with_message(self) -> None:
        """ExtractionErrorにメッセージを設定できる"""
        error = ExtractionError("テスト用エラー")
        assert str(error) == "テスト用エラー"
