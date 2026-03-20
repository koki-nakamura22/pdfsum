"""OpenAISummarizer のユニットテスト"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pdfsum.engines.openai import (
    DEFAULT_OPENAI_MODEL,
    OPENAI_MODEL_SPECS,
    OpenAISummarizer,
)
from pdfsum.models.summary import SummarizationError


class TestOpenAISummarizer:
    """OpenAISummarizer のテスト"""

    def setup_method(self) -> None:
        self.engine = OpenAISummarizer(api_key="test-key", model="gpt-4.1-mini")

    def test_get_model_name_returns_model(self) -> None:
        assert self.engine.get_model_name() == "gpt-4.1-mini"

    def test_get_max_input_tokens_returns_spec_value(self) -> None:
        assert self.engine.get_max_input_tokens() == 1_047_576

    def test_default_model_is_used_when_no_model_specified(self) -> None:
        engine = OpenAISummarizer(api_key="test-key")
        assert engine.get_model_name() == DEFAULT_OPENAI_MODEL

    @pytest.mark.parametrize(
        ("model", "specs"),
        OPENAI_MODEL_SPECS.items(),
    )
    def test_all_supported_models_have_correct_specs(
        self, model: str, specs: dict[str, int]
    ) -> None:
        engine = OpenAISummarizer(api_key="test-key", model=model)
        assert engine.get_model_name() == model
        assert engine.get_max_input_tokens() == specs["max_input_tokens"]
        assert engine._specs["max_output_tokens"] == specs["max_output_tokens"]

    def test_unsupported_model_raises_error(self) -> None:
        with pytest.raises(SummarizationError, match="未対応のOpenAIモデル"):
            OpenAISummarizer(api_key="test-key", model="gpt-unknown")

    @patch("pdfsum.engines.openai.httpx.post")
    def test_summarize_returns_summary_text(self, mock_post: MagicMock) -> None:
        """正常なAPIレスポンスで要約テキストを返す"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenAI要約テキスト"}}]
        }
        mock_post.return_value = mock_response

        result = self.engine.summarize("テスト用テキスト", "standard")

        assert result == "OpenAI要約テキスト"
        call_kwargs = mock_post.call_args
        assert "Bearer" in call_kwargs.kwargs["headers"]["Authorization"]

    @patch("pdfsum.engines.openai.httpx.post")
    def test_summarize_with_http_error_raises_summarization_error(
        self, mock_post: MagicMock
    ) -> None:
        """HTTP通信エラーでSummarizationErrorを送出する"""
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SummarizationError, match="通信に失敗しました"):
            self.engine.summarize("テスト", "standard")

    @patch("pdfsum.engines.openai.httpx.post")
    def test_summarize_with_500_error_raises_summarization_error(
        self, mock_post: MagicMock
    ) -> None:
        """500エラーでSummarizationErrorを送出する"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with pytest.raises(SummarizationError, match="ステータス 500"):
            self.engine.summarize("テスト", "standard")

    @patch("pdfsum.engines.openai.httpx.post")
    @patch("pdfsum.engines.base.time.sleep")
    def test_summarize_retries_on_429(
        self, mock_sleep: MagicMock, mock_post: MagicMock
    ) -> None:
        """429レート制限でリトライする"""
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.text = "Rate limited"

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "リトライ後の要約"}}]
        }

        mock_post.side_effect = [rate_limit_response, success_response]

        result = self.engine.summarize("テスト", "standard")

        assert result == "リトライ後の要約"
        assert mock_post.call_count == 2

    def test_summarize_with_invalid_length_raises_summarization_error(self) -> None:
        """無効な要約長でSummarizationErrorを送出する"""
        with pytest.raises(SummarizationError, match="無効な要約長です"):
            self.engine.summarize("テスト", "invalid")

    @patch("pdfsum.engines.openai.httpx.post")
    def test_summarize_with_invalid_response_raises_summarization_error(
        self, mock_post: MagicMock
    ) -> None:
        """不正なレスポンス構造でSummarizationErrorを送出する"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}
        mock_post.return_value = mock_response

        with pytest.raises(SummarizationError, match="レスポンス解析に失敗"):
            self.engine.summarize("テスト", "standard")
