"""Anthropic Claude APIを使用した要約エンジン"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from pdfsum.engines.base import (
    SummarizerEngine,
    get_prompt_for_length,
    retry_on_rate_limit,
)
from pdfsum.models.summary import SummarizationError

if TYPE_CHECKING:
    from pdfsum.config.manager import SummaryConfig

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_TIMEOUT_SECONDS = 120
CLAUDE_API_VERSION = "2023-06-01"

CLAUDE_MODEL_SPECS: dict[str, dict[str, int]] = {
    "claude-opus-4-6": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 128_000,
    },
    "claude-sonnet-4-6": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 64_000,
    },
    "claude-haiku-4-5-20251001": {
        "max_input_tokens": 200_000,
        "max_output_tokens": 64_000,
    },
}

SUPPORTED_CLAUDE_MODELS = frozenset(CLAUDE_MODEL_SPECS.keys())


class ClaudeSummarizer(SummarizerEngine):
    """Anthropic Claude APIを使用した要約エンジン"""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_CLAUDE_MODEL,
        summary_config: SummaryConfig | None = None,
    ) -> None:
        if model not in SUPPORTED_CLAUDE_MODELS:
            raise SummarizationError(
                f"未対応のClaudeモデルです: {model}"
                f"（対応モデル: {', '.join(sorted(SUPPORTED_CLAUDE_MODELS))}）"
            )
        self._api_key = api_key
        self._model = model
        self._specs = CLAUDE_MODEL_SPECS[model]
        self._summary_config = summary_config

    @retry_on_rate_limit
    def summarize(self, text: str, length: str) -> str:
        """Claude APIでテキストを要約する。

        Args:
            text: 要約対象のテキスト
            length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約テキスト

        Raises:
            SummarizationError: API通信エラーまたは要約生成失敗
        """
        prompt = get_prompt_for_length(length, self._summary_config)

        payload = {
            "model": self._model,
            "max_tokens": self._specs["max_output_tokens"],
            "messages": [
                {
                    "role": "user",
                    "content": f"{prompt}\n\n---\n\n{text}",
                }
            ],
        }

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": CLAUDE_API_VERSION,
            "content-type": "application/json",
        }

        try:
            response = httpx.post(
                CLAUDE_API_URL,
                json=payload,
                headers=headers,
                timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise SummarizationError(
                f"LLM APIとの通信に失敗しました: {e}"
            ) from e

        if response.status_code == 429:
            raise SummarizationError(
                f"APIレート制限に達しました (429): {response.text}"
            )

        if response.status_code != 200:
            raise SummarizationError(
                f"LLM APIとの通信に失敗しました: "
                f"ステータス {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            result: str = data["content"][0]["text"]
            return result
        except (KeyError, IndexError, ValueError) as e:
            raise SummarizationError(
                f"LLM APIのレスポンス解析に失敗しました: {e}"
            ) from e

    def get_model_name(self) -> str:
        return self._model

    def get_max_input_tokens(self) -> int:
        return self._specs["max_input_tokens"]
