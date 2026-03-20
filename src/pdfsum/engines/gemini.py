"""Google Gemini APIを使用した要約エンジン"""

import httpx

from pdfsum.engines.base import (
    SummarizerEngine,
    get_prompt_for_length,
    retry_on_rate_limit,
)
from pdfsum.models.summary import SummarizationError

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TIMEOUT_SECONDS = 120

GEMINI_MODEL_SPECS: dict[str, dict[str, int]] = {
    "gemini-2.5-flash": {
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535,
    },
    "gemini-2.5-flash-lite": {
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535,
    },
    "gemini-2.5-pro": {
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535,
    },
}

SUPPORTED_GEMINI_MODELS = frozenset(GEMINI_MODEL_SPECS.keys())


class GeminiSummarizer(SummarizerEngine):
    """Google Gemini APIを使用した要約エンジン"""

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
        if model not in SUPPORTED_GEMINI_MODELS:
            raise SummarizationError(
                f"未対応のGeminiモデルです: {model}"
                f"（対応モデル: {', '.join(sorted(SUPPORTED_GEMINI_MODELS))}）"
            )
        self._api_key = api_key
        self._model = model
        self._specs = GEMINI_MODEL_SPECS[model]

    @retry_on_rate_limit
    def summarize(self, text: str, length: str) -> str:
        """Gemini APIでテキストを要約する。

        Args:
            text: 要約対象のテキスト
            length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約テキスト

        Raises:
            SummarizationError: API通信エラーまたは要約生成失敗
        """
        prompt = get_prompt_for_length(length)
        url = f"{GEMINI_API_URL}/{self._model}:generateContent"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{prompt}\n\n---\n\n{text}"},
                    ]
                }
            ],
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                params={"key": self._api_key},
                timeout=GEMINI_TIMEOUT_SECONDS,
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
            result: str = data["candidates"][0]["content"]["parts"][0]["text"]
            return result
        except (KeyError, IndexError, ValueError) as e:
            raise SummarizationError(
                f"LLM APIのレスポンス解析に失敗しました: {e}"
            ) from e

    def get_model_name(self) -> str:
        return self._model

    def get_max_input_tokens(self) -> int:
        return self._specs["max_input_tokens"]
