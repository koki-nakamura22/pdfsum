"""SummarizerFactory のユニットテスト"""

import pytest

from pdfsum.engines.claude import ClaudeSummarizer
from pdfsum.engines.factory import SummarizerFactory
from pdfsum.engines.gemini import GeminiSummarizer
from pdfsum.engines.openai import OpenAISummarizer
from pdfsum.models.summary import ConfigError


class TestSummarizerFactory:
    """SummarizerFactory のテスト"""

    def test_create_gemini_returns_gemini_summarizer(self) -> None:
        """geminiプロバイダでGeminiSummarizerを返す"""
        engine = SummarizerFactory.create("gemini", "key", "gemini-2.5-flash")

        assert isinstance(engine, GeminiSummarizer)
        assert engine.get_model_name() == "gemini-2.5-flash"

    def test_create_claude_returns_claude_summarizer(self) -> None:
        """claudeプロバイダでClaudeSummarizerを返す"""
        engine = SummarizerFactory.create("claude", "key", "claude-sonnet-4-6")

        assert isinstance(engine, ClaudeSummarizer)
        assert engine.get_model_name() == "claude-sonnet-4-6"

    def test_create_openai_returns_openai_summarizer(self) -> None:
        """openaiプロバイダでOpenAISummarizerを返す"""
        engine = SummarizerFactory.create("openai", "key", "gpt-4.1-mini")

        assert isinstance(engine, OpenAISummarizer)
        assert engine.get_model_name() == "gpt-4.1-mini"

    def test_create_unknown_provider_raises_config_error(self) -> None:
        """未対応プロバイダでConfigErrorを送出する"""
        with pytest.raises(ConfigError, match="未対応のLLMプロバイダです"):
            SummarizerFactory.create("unknown", "key", "model")
