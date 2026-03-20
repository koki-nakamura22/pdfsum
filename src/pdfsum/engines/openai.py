"""OpenAI APIを使用した要約エンジン"""

import httpx

from pdfsum.engines.base import (
    SummarizerEngine,
    get_prompt_for_length,
    retry_on_rate_limit,
)
from pdfsum.models.summary import SummarizationError

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 120

OPENAI_MODEL_SPECS: dict[str, dict[str, int]] = {
    "gpt-5.4": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 128_000,
    },
    "gpt-5.4-mini": {
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
    },
    "gpt-5.4-nano": {
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
    },
    "gpt-4.1": {
        "max_input_tokens": 1_047_576,
        "max_output_tokens": 32_768,
    },
    "gpt-4.1-mini": {
        "max_input_tokens": 1_047_576,
        "max_output_tokens": 32_768,
    },
    "gpt-4.1-nano": {
        "max_input_tokens": 1_047_576,
        "max_output_tokens": 32_768,
    },
}

SUPPORTED_OPENAI_MODELS = frozenset(OPENAI_MODEL_SPECS.keys())


class OpenAISummarizer(SummarizerEngine):
    """OpenAI APIを使用した要約エンジン"""

    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> None:
        if model not in SUPPORTED_OPENAI_MODELS:
            raise SummarizationError(
                f"未対応のOpenAIモデルです: {model}"
                f"（対応モデル: {', '.join(sorted(SUPPORTED_OPENAI_MODELS))}）"
            )
        self._api_key = api_key
        self._model = model
        self._specs = OPENAI_MODEL_SPECS[model]

    @retry_on_rate_limit
    def summarize(self, text: str, length: str) -> str:
        """OpenAI APIでテキストを要約する。

        Args:
            text: 要約対象のテキスト
            length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約テキスト

        Raises:
            SummarizationError: API通信エラーまたは要約生成失敗
        """
        prompt = get_prompt_for_length(length)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                OPENAI_API_URL,
                json=payload,
                headers=headers,
                timeout=OPENAI_TIMEOUT_SECONDS,
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
            result: str = data["choices"][0]["message"]["content"]
            return result
        except (KeyError, IndexError, ValueError) as e:
            raise SummarizationError(
                f"LLM APIのレスポンス解析に失敗しました: {e}"
            ) from e

    def get_model_name(self) -> str:
        return self._model

    def get_max_input_tokens(self) -> int:
        return self._specs["max_input_tokens"]
