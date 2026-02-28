"""GeminiSummarizer のユニットテスト"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pdfsum.engines.gemini import GeminiSummarizer
from pdfsum.models.summary import SummarizationError


class TestGeminiSummarizer:
    """GeminiSummarizer のテスト"""

    def setup_method(self) -> None:
        self.engine = GeminiSummarizer(api_key="test-key", model="gemini-2.5-flash")

    def test_get_model_name_returns_model(self) -> None:
        assert self.engine.get_model_name() == "gemini-2.5-flash"

    def test_get_max_input_tokens_returns_1m(self) -> None:
        assert self.engine.get_max_input_tokens() == 1_000_000

    @patch("pdfsum.engines.gemini.httpx.post")
    def test_summarize_returns_summary_text(self, mock_post: MagicMock) -> None:
        """正常なAPIレスポンスで要約テキストを返す"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "要約テキスト"}]}}
            ]
        }
        mock_post.return_value = mock_response

        result = self.engine.summarize("テスト用テキスト", "standard")

        assert result == "要約テキスト"
        mock_post.assert_called_once()

    @patch("pdfsum.engines.gemini.httpx.post")
    def test_summarize_with_http_error_raises_summarization_error(
        self, mock_post: MagicMock
    ) -> None:
        """HTTP通信エラーでSummarizationErrorを送出する"""
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SummarizationError, match="通信に失敗しました"):
            self.engine.summarize("テスト", "standard")

    @patch("pdfsum.engines.gemini.httpx.post")
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

    @patch("pdfsum.engines.gemini.httpx.post")
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

    @patch("pdfsum.engines.gemini.httpx.post")
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
            "candidates": [
                {"content": {"parts": [{"text": "リトライ後の要約"}]}}
            ]
        }

        mock_post.side_effect = [rate_limit_response, success_response]

        result = self.engine.summarize("テスト", "standard")

        assert result == "リトライ後の要約"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()
