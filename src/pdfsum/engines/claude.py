"""Anthropic Claude APIを使用した要約エンジン"""

import httpx

from pdfsum.engines.base import (
    SUMMARY_PROMPTS,
    SummarizerEngine,
    retry_on_rate_limit,
)
from pdfsum.models.summary import SummarizationError

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_MAX_INPUT_TOKENS = 200_000
CLAUDE_TIMEOUT_SECONDS = 120
CLAUDE_API_VERSION = "2023-06-01"
CLAUDE_MAX_OUTPUT_TOKENS = 8192


class ClaudeSummarizer(SummarizerEngine):
    """Anthropic Claude APIを使用した要約エンジン"""

    def __init__(self, api_key: str, model: str = DEFAULT_CLAUDE_MODEL) -> None:
        self._api_key = api_key
        self._model = model

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
        prompt = SUMMARY_PROMPTS[length]

        payload = {
            "model": self._model,
            "max_tokens": CLAUDE_MAX_OUTPUT_TOKENS,
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
        return CLAUDE_MAX_INPUT_TOKENS
