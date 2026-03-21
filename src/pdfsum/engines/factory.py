"""要約エンジンのファクトリ"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfsum.engines.base import SummarizerEngine
from pdfsum.engines.claude import ClaudeSummarizer
from pdfsum.engines.gemini import GeminiSummarizer
from pdfsum.engines.openai import OpenAISummarizer
from pdfsum.models.summary import ConfigError

if TYPE_CHECKING:
    from pdfsum.config.manager import SummaryConfig

SUPPORTED_PROVIDERS = ("gemini", "claude", "openai")


class SummarizerFactory:
    """設定に基づいて適切な要約エンジンを生成するファクトリ"""

    @staticmethod
    def create(
        provider: str,
        api_key: str,
        model: str | None = None,
        summary_config: SummaryConfig | None = None,
    ) -> SummarizerEngine:
        """プロバイダ名に基づいて要約エンジンを生成する。

        Args:
            provider: LLMプロバイダ名 ("gemini", "claude", "openai")
            api_key: APIキー
            model: モデル名。未指定時は各エンジンのデフォルトモデルを使用
            summary_config: 要約設定（カスタムプロンプト等）

        Returns:
            要約エンジンのインスタンス

        Raises:
            ConfigError: 未対応のプロバイダが指定された場合
        """
        kwargs: dict[str, object] = {
            "api_key": api_key,
            "summary_config": summary_config,
        }
        if model is not None:
            kwargs["model"] = model

        if provider == "gemini":
            return GeminiSummarizer(**kwargs)  # type: ignore[arg-type]
        elif provider == "claude":
            return ClaudeSummarizer(**kwargs)  # type: ignore[arg-type]
        elif provider == "openai":
            return OpenAISummarizer(**kwargs)  # type: ignore[arg-type]
        else:
            raise ConfigError(
                f"未対応のLLMプロバイダです: {provider}"
                f"（対応プロバイダ: {', '.join(SUPPORTED_PROVIDERS)}）"
            )
