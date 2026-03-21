"""pdfsum - PDFドキュメント要約CLIツール"""

from __future__ import annotations

import os

from pdfsum.models.summary import (
    ConfigError,
    ExtractionError,
    PdfsumError,
    SummarizationError,
    Summary,
)
from pdfsum.services.summarize_service import SummarizeService

__version__ = "0.1.0"

__all__ = [
    "create_service",
    "SummarizeService",
    "Summary",
    "PdfsumError",
    "ConfigError",
    "ExtractionError",
    "SummarizationError",
]


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
    from pdfsum.config.manager import (
        DEFAULT_DB_PATH,
        DEFAULT_MODELS,
        DEFAULT_PROVIDER_CONFIGS,
        ConfigManager,
        SummaryConfig,
    )
    from pdfsum.engines.factory import SummarizerFactory
    from pdfsum.extractors.pdf_extractor import PDFExtractor
    from pdfsum.repositories.sqlite import SQLiteSummaryRepository

    if provider is None:
        # config.tomlから設定を取得
        config_manager = ConfigManager()
        config = config_manager.load()
        resolved_provider = config.llm.provider
        resolved_api_key = config_manager.get_api_key(config, resolved_provider)
        resolved_model = model or config.llm.model
        resolved_db_path = db_path or config.database.path
        summary_config = config.summary
        if extra_instructions is not None:
            summary_config = SummaryConfig(
                default_length=summary_config.default_length,
                extra_instructions=extra_instructions,
                prompt_short=summary_config.prompt_short,
                prompt_standard=summary_config.prompt_standard,
                prompt_detailed=summary_config.prompt_detailed,
            )
    else:
        # provider指定あり: 直接構築
        resolved_provider = provider

        if api_key is not None:
            resolved_api_key = api_key
        else:
            # 環境変数フォールバック
            env_var = DEFAULT_PROVIDER_CONFIGS.get(provider)
            if env_var is None:
                raise ConfigError(f"未対応のLLMプロバイダです: {provider}")
            resolved_api_key = os.environ.get(env_var, "")
            if not resolved_api_key:
                raise ConfigError(
                    f"APIキーが設定されていません。"
                    f"環境変数 {env_var} を設定するか、api_key引数を指定してください"
                )

        resolved_model = model or DEFAULT_MODELS.get(provider, "")
        if not resolved_model:
            raise ConfigError(
                "モデルが指定されていません。model引数を指定してください"
            )

        from pathlib import Path

        resolved_db_path = (
            str(Path(db_path).expanduser()) if db_path else
            str(Path(DEFAULT_DB_PATH).expanduser())
        )

        summary_config = SummaryConfig(
            extra_instructions=extra_instructions or "",
        )

    engine = SummarizerFactory.create(
        resolved_provider, resolved_api_key, resolved_model, summary_config
    )
    extractor = PDFExtractor()
    repository = SQLiteSummaryRepository(resolved_db_path)

    return SummarizeService(extractor, engine, repository)
