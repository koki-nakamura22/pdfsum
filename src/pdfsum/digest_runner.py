"""digestkitベースの一括PDF要約ランナー。

pdfsumをdigestkit (https://github.com/koki-nakamura22/inboxkit) のパイプラインへ
適用したドッグフーディング実装。指定ディレクトリ配下のPDFを
``LocalDirectorySource → PDFExtractor → LLMSummarizer → SQLiteSink`` の
1:1パイプラインで処理する。

既存の ``pdfsum summarize`` (単一PDF + 長さ指定 + チャンク分割) とは独立した
batch処理パスとして提供しており、digestkitのフレームワークが実用上ちゃんと
組み立てられるかを検証する目的を持つ。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# NOTE: digestkit 0.1.0 は `digestkit.sources.__init__` で `NotionDatabaseSource`
# を eager import するため、`notion` extra を必ずインストールする必要がある
# (本リポジトリの pyproject.toml で `digestkit[pdf,notion]` 指定済み)。
# upstream で sources の lazy import が整備されたら notion extra は外せる。
from digestkit import Digester
from digestkit.extractors import PDFExtractor as DigestKitPDFExtractor
from digestkit.sinks import SQLiteSink
from digestkit.sources import LocalDirectorySource
from digestkit.summarizers import LLMSummarizer

from pdfsum.config.manager import Config, ConfigManager
from pdfsum.models.summary import ConfigError

if TYPE_CHECKING:
    from digestkit import RunResult

# pdfsumのprovider名 → litellmのprovider名
_PROVIDER_TO_LITELLM: dict[str, str] = {
    "gemini": "gemini",
    "claude": "anthropic",
    "openai": "openai",
}

_DEFAULT_PROMPT = (
    "以下のドキュメントを日本語で簡潔に要約してください。\n\n{text}"
)


def build_digester(
    directory: Path,
    *,
    glob: str = "*.pdf",
    db_path: Path | str | None = None,
    config: Config | None = None,
) -> Digester:
    """pdfsum設定からdigestkit Digesterを組み立てる。

    Args:
        directory: スキャン対象ディレクトリ
        glob: 対象ファイルglobパターン（デフォルト ``*.pdf``）
        db_path: 要約結果の出力SQLiteパス。未指定時はカレントの ``digests.db``
        config: 既にロード済みの :class:`Config`。
            未指定時は :class:`ConfigManager` で読み込む

    Returns:
        実行可能な :class:`digestkit.Digester` インスタンス

    Raises:
        ConfigError: APIキーが取得できない、または未対応プロバイダの場合
    """
    cfg_manager = ConfigManager()
    cfg = config or cfg_manager.load()

    provider = cfg.llm.provider
    _litellm_provider = _PROVIDER_TO_LITELLM.get(provider)
    if _litellm_provider is None:
        raise ConfigError(f"digestkitに未対応のプロバイダです: {provider}")
    litellm_provider: str = _litellm_provider

    api_key = cfg_manager.get_api_key(cfg, provider)

    user_prompt = _DEFAULT_PROMPT
    if cfg.summary.extra_instructions:
        user_prompt = (
            f"{cfg.summary.extra_instructions}\n\n以下のドキュメントを"
            f"日本語で簡潔に要約してください。\n\n{{text}}"
        )

    sink_path = Path(db_path) if db_path is not None else Path("digests.db")

    # litellmはOSの環境変数からAPIキーを拾う仕様。pdfsum側で取得済みのキーを
    # 該当プロバイダ標準の環境変数名に流し込む（既存値があればそれを優先）。
    import os

    env_var = {
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }[litellm_provider]
    os.environ.setdefault(env_var, api_key)

    class _PdfsumDigester(Digester):
        source = LocalDirectorySource(directory, glob=glob)
        extractor = DigestKitPDFExtractor()
        summarizer = LLMSummarizer(
            provider=litellm_provider,
            model=cfg.llm.model,
            user_prompt_template=user_prompt,
        )
        sink = SQLiteSink(sink_path)

    return _PdfsumDigester()


def run_digest(
    directory: Path,
    *,
    glob: str = "*.pdf",
    db_path: Path | str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RunResult:
    """digestkit Digesterを構築して実行するワンショット関数。"""
    digester = build_digester(directory, glob=glob, db_path=db_path)
    return digester.run(limit=limit, dry_run=dry_run)
