"""要約エンジンのファクトリ"""

from pdfsum.engines.base import SummarizerEngine
from pdfsum.engines.claude import ClaudeSummarizer
from pdfsum.engines.gemini import GeminiSummarizer
from pdfsum.engines.openai import OpenAISummarizer
from pdfsum.models.summary import ConfigError

SUPPORTED_PROVIDERS = ("gemini", "claude", "openai")


class SummarizerFactory:
    """設定に基づいて適切な要約エンジンを生成するファクトリ"""

    @staticmethod
    def create(provider: str, api_key: str, model: str) -> SummarizerEngine:
        """プロバイダ名に基づいて要約エンジンを生成する。

        Args:
            provider: LLMプロバイダ名 ("gemini", "claude", "openai")
            api_key: APIキー
            model: モデル名

        Returns:
            要約エンジンのインスタンス

        Raises:
            ConfigError: 未対応のプロバイダが指定された場合
        """
        if provider == "gemini":
            return GeminiSummarizer(api_key=api_key, model=model)
        elif provider == "claude":
            return ClaudeSummarizer(api_key=api_key, model=model)
        elif provider == "openai":
            return OpenAISummarizer(api_key=api_key, model=model)
        else:
            raise ConfigError(
                f"未対応のLLMプロバイダです: {provider}"
                f"（対応プロバイダ: {', '.join(SUPPORTED_PROVIDERS)}）"
            )
