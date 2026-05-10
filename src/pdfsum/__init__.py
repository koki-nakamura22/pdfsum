"""pdfsum - PDFドキュメント要約CLIツール"""

from __future__ import annotations

import os
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING

from pdfsum.models.summary import (
    ConfigError,
    ExtractionError,
    PdfsumError,
    SummarizationError,
    Summary,
)

if TYPE_CHECKING:
    from pdfsum.services.summarize_service import SummarizeService

__version__ = _pkg_version("pdfsum")

__all__ = [
    "create_service",
    "SummarizeService",
    "Summary",
    "PdfsumError",
    "ConfigError",
    "ExtractionError",
    "SummarizationError",
]


def __getattr__(name: str) -> object:
    if name == "SummarizeService":
        from pdfsum.services.summarize_service import SummarizeService
        return SummarizeService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_service(
    provider: str | None = None,
    api_key: str | None = None,
    *,
    model: str | None = None,
    db_path: str | None = None,
    extra_instructions: str | None = None,
) -> SummarizeService:
    """SummarizeServiceのファクトリ関数。

    引数なしで呼び出すとconfig.tomlの設定を使用する。
    provider/api_keyを指定するとconfig.toml不要で直接構築できる。

    Args:
        provider: LLMプロバイダ名 ("gemini", "claude", "openai")。
            未指定時はconfig.tomlから取得。
        api_key: APIキー。未指定時は環境変数から取得。
        model: モデル名。未指定時はプロバイダのデフォルトモデルを使用。
        db_path: データベースファイルのパス。未指定時はデフォルトパスを使用。
        extra_instructions: 要約プロンプトへの追加指示。

    Returns:
        構築済みのSummarizeServiceインスタンス

    Raises:
        ConfigError: 設定の読み込みやAPIキーの取得に失敗した場合
    """
    from pathlib import Path as _Path

    from pdfsum.config.manager import (
        DEFAULT_MODEL,
        DEFAULT_PROVIDER_CONFIGS,
        Config,
        ConfigManager,
        DatabaseConfig,
        LLMConfig,
        SummaryConfig,
        get_default_db_path,
    )
    from pdfsum.services.summarize_service import SummarizeService as _SummarizeService

    if provider is None:
        config_manager = ConfigManager()
        config = config_manager.load()
        resolved_provider = config.llm.provider
        resolved_api_key = api_key or config_manager.get_api_key(config, resolved_provider)
        resolved_model = model or config.llm.model
        resolved_db_path = db_path or config.database.path
        summary_config = config.summary
        if extra_instructions is not None:
            summary_config = SummaryConfig(
                default_length=summary_config.default_length,
                extra_instructions=extra_instructions,
                chunked=summary_config.chunked,
            )
        built_config = Config(
            llm=LLMConfig(provider=resolved_provider, model=resolved_model),
            summary=summary_config,
            database=DatabaseConfig(path=resolved_db_path),
        )
    else:
        if api_key is not None:
            resolved_api_key = api_key
        else:
            env_var = DEFAULT_PROVIDER_CONFIGS.get(provider)
            if env_var is None:
                raise ConfigError(f"未対応のLLMプロバイダです: {provider}")
            resolved_api_key = os.environ.get(env_var, "")
            if not resolved_api_key:
                raise ConfigError(
                    f"APIキーが設定されていません。"
                    f"環境変数 {env_var} を設定するか、api_key引数を指定してください"
                )

        resolved_db_path = (
            str(_Path(db_path).expanduser()) if db_path else get_default_db_path()
        )
        built_config = Config(
            llm=LLMConfig(provider=provider, model=model or DEFAULT_MODEL),
            summary=SummaryConfig(extra_instructions=extra_instructions or ""),
            database=DatabaseConfig(path=resolved_db_path),
        )

    # digestkit/litellm は env vars から API キーを読むので事前に設定する
    env_var_name = DEFAULT_PROVIDER_CONFIGS.get(built_config.llm.provider, "")
    if env_var_name and resolved_api_key:
        os.environ[env_var_name] = resolved_api_key

    return _SummarizeService(config=built_config)
