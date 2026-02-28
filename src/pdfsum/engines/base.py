"""要約エンジンの抽象基底クラスと共通定義"""

import time
from abc import ABC, abstractmethod

from pdfsum.models.summary import SummarizationError

MAX_RETRY_COUNT = 3
RETRY_BASE_DELAY_SECONDS = 1

SUMMARY_PROMPTS: dict[str, str] = {
    "short": (
        "以下のテキストの要点のみを箇条書きで簡潔に要約してください。"
        "300〜500文字程度で、最も重要なポイントだけを抽出してください。"
        "日本語で出力してください。"
    ),
    "standard": (
        "以下のテキストの要点と重要な詳細を含めて要約してください。"
        "1000〜2000文字程度で、主要な論点と補足情報を整理してください。"
        "日本語で出力してください。"
    ),
    "detailed": (
        "以下のテキストを章・セクションごとに概要と要点を含めて詳細に要約してください。"
        "3000〜5000文字程度で、構造を保ちながら網羅的に要約してください。"
        "日本語で出力してください。"
    ),
}

VALID_LENGTHS = frozenset(SUMMARY_PROMPTS.keys())


def get_prompt_for_length(length: str) -> str:
    """要約長に対応するプロンプトを取得する。

    Args:
        length: 要約の長さ ("short", "standard", "detailed")

    Returns:
        プロンプト文字列

    Raises:
        SummarizationError: 無効な要約長が指定された場合
    """
    if length not in VALID_LENGTHS:
        raise SummarizationError(
            f"無効な要約長です: {length}"
            f"（有効な値: {', '.join(sorted(VALID_LENGTHS))}）"
        )
    return SUMMARY_PROMPTS[length]


class SummarizerEngine(ABC):
    """要約エンジンの抽象基底クラス"""

    @abstractmethod
    def summarize(self, text: str, length: str) -> str:
        """テキストを要約する。

        Args:
            text: 要約対象のテキスト
            length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約テキスト

        Raises:
            SummarizationError: 要約生成に失敗した場合
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """使用モデル名を返す"""
        ...

    @abstractmethod
    def get_max_input_tokens(self) -> int:
        """最大入力トークン数を返す"""
        ...


def retry_on_rate_limit(func):  # type: ignore[no-untyped-def]
    """HTTP 429レート制限時に指数バックオフでリトライするデコレータ"""

    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRY_COUNT + 1):
            try:
                return func(*args, **kwargs)
            except SummarizationError as e:
                if "429" in str(e) and attempt < MAX_RETRY_COUNT:
                    delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    time.sleep(delay)
                    last_exception = e
                    continue
                raise
        raise last_exception  # type: ignore[misc]

    return wrapper
