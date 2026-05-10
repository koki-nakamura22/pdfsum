"""pdfsum 公開例外階層 + digestkit 例外マッピングヘルパ.

`PdfsumError` / `ConfigError` / `ExtractionError` / `SummarizationError` は
`pdfsum.__all__` 経由で公開された **公開 API** であり、削除・改名禁止。
digestkit 由来の同名例外を catch して pdfsum 側でラップする経路で使われる。
"""
from __future__ import annotations

from digestkit import ConfigurationError as _DkConfigurationError
from digestkit import DigestkitError as _DkDigestkitError
from digestkit.sinks import SinkError as _DkSinkError
from digestkit.summarizers import SummarizationError as _DkSummarizationError


class PdfsumError(Exception):
    """pdfsum 例外階層の基底 (公開 API)."""


class ConfigError(PdfsumError):
    """設定ファイル / 環境変数の読み込み・検証失敗 (公開 API)."""


class ExtractionError(PdfsumError):
    """PDF テキスト抽出失敗 (公開 API).

    digestkit の Extractor 失敗を raise する経路で使われる。
    """


class SummarizationError(PdfsumError):
    """LLM 要約失敗 (公開 API).

    digestkit の `digestkit.summarizers.SummarizationError` を catch して
    本例外でラップする経路で使われる。
    """


__all__ = [
    "ConfigError",
    "ExtractionError",
    "PdfsumError",
    "SummarizationError",
    "exit_code_for",
    "format_digestkit_error",
]


def format_digestkit_error(exc: BaseException) -> str:
    """digestkit 由来例外 (または同等の pdfsum 例外) を CLI 表示用文字列に整形."""
    if isinstance(exc, ConfigError | _DkConfigurationError):
        return f"エラー: 設定または digestkit の組み立てに失敗しました: {exc}"
    if isinstance(exc, SummarizationError | _DkSummarizationError):
        return f"エラー: 要約に失敗しました: {exc}"
    if isinstance(exc, ExtractionError):
        return f"エラー: PDF テキスト抽出に失敗しました: {exc}"
    if isinstance(exc, _DkSinkError):
        return f"エラー: DB への書き込みに失敗しました: {exc}"
    if isinstance(exc, PdfsumError):
        return f"エラー: {exc}"
    if isinstance(exc, _DkDigestkitError):
        return f"エラー: digestkit 処理失敗 ({type(exc).__name__}): {exc}"
    return f"予期しない失敗 ({type(exc).__name__}): {exc}"


def exit_code_for(exc: BaseException) -> int:
    """例外から終了コードを決定する."""
    if isinstance(exc, ConfigError | _DkConfigurationError):
        return 2
    return 1
