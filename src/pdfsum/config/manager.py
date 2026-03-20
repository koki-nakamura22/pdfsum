"""設定管理"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from pdfsum.models.summary import ConfigError

DEFAULT_CONFIG_PATH = "~/.config/pdfsum/config.toml"
DEFAULT_DB_PATH = "~/.local/share/pdfsum/summaries.db"
DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_SUMMARY_LENGTH = "standard"

DEFAULT_PROVIDER_CONFIGS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass
class ProviderConfig:
    """LLMプロバイダの設定"""

    api_key_env: str


@dataclass
class LLMConfig:
    """LLM設定"""

    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.providers:
            self.providers = {
                name: ProviderConfig(api_key_env=env_var)
                for name, env_var in DEFAULT_PROVIDER_CONFIGS.items()
            }


@dataclass
class SummaryConfig:
    """要約設定"""

    default_length: str = DEFAULT_SUMMARY_LENGTH
    extra_instructions: str = ""
    prompt_short: str = ""
    prompt_standard: str = ""
    prompt_detailed: str = ""


@dataclass
class DatabaseConfig:
    """データベース設定"""

    path: str = DEFAULT_DB_PATH

    def __post_init__(self) -> None:
        self.path = str(Path(self.path).expanduser())


@dataclass
class Config:
    """アプリケーション設定"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


class ConfigManager:
    """設定ファイル（TOML）の読み込みとAPIキー管理"""

    def __init__(
        self,
        config_path: str | None = None,
        env_path: str | None = None,
    ) -> None:
        resolved = config_path or os.environ.get(
            "PDFSUM_CONFIG_PATH", DEFAULT_CONFIG_PATH
        )
        self._config_path = Path(resolved).expanduser()
        resolved_env = env_path or os.environ.get("PDFSUM_ENV_PATH")
        self._env_path = resolved_env

    def load(self) -> Config:
        """設定を読み込む。ファイルがなければデフォルト設定を返す。

        .envファイルが存在する場合、環境変数として読み込む。

        Returns:
            設定オブジェクト

        Raises:
            ConfigError: 設定ファイルの読み込みに失敗した場合
        """
        load_dotenv(dotenv_path=self._env_path)

        if not self._config_path.exists():
            return Config()

        try:
            with open(self._config_path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ConfigError(
                f"設定ファイルの読み込みに失敗しました: {e}"
            ) from e

        return self._parse_config(data)

    def _parse_config(self, data: dict[str, object]) -> Config:
        """TOMLデータからConfigオブジェクトを構築する"""
        llm_data = data.get("llm", {})
        if not isinstance(llm_data, dict):
            llm_data = {}

        summary_data = data.get("summary", {})
        if not isinstance(summary_data, dict):
            summary_data = {}

        db_data = data.get("database", {})
        if not isinstance(db_data, dict):
            db_data = {}

        # LLMプロバイダ設定の解析
        providers: dict[str, ProviderConfig] = {}
        for provider_name, default_env in DEFAULT_PROVIDER_CONFIGS.items():
            provider_data = llm_data.get(provider_name, {})
            if isinstance(provider_data, dict):
                api_key_env = provider_data.get("api_key_env", default_env)
                if isinstance(api_key_env, str):
                    providers[provider_name] = ProviderConfig(
                        api_key_env=api_key_env
                    )
                else:
                    providers[provider_name] = ProviderConfig(
                        api_key_env=default_env
                    )
            else:
                providers[provider_name] = ProviderConfig(
                    api_key_env=default_env
                )

        provider_str = llm_data.get("provider", DEFAULT_PROVIDER)
        model_str = llm_data.get("model", DEFAULT_MODEL)
        length_str = summary_data.get("default_length", DEFAULT_SUMMARY_LENGTH)
        extra_instructions = summary_data.get("extra_instructions", "")
        prompt_short = summary_data.get("prompt_short", "")
        prompt_standard = summary_data.get("prompt_standard", "")
        prompt_detailed = summary_data.get("prompt_detailed", "")
        db_path_str = db_data.get("path", DEFAULT_DB_PATH)

        return Config(
            llm=LLMConfig(
                provider=str(provider_str),
                model=str(model_str),
                providers=providers,
            ),
            summary=SummaryConfig(
                default_length=str(length_str),
                extra_instructions=str(extra_instructions),
                prompt_short=str(prompt_short),
                prompt_standard=str(prompt_standard),
                prompt_detailed=str(prompt_detailed),
            ),
            database=DatabaseConfig(
                path=str(db_path_str),
            ),
        )

    def get_api_key(self, config: Config, provider: str) -> str:
        """指定プロバイダのAPIキーを環境変数から取得する。

        Args:
            config: 設定オブジェクト
            provider: LLMプロバイダ名

        Returns:
            APIキー文字列

        Raises:
            ConfigError: APIキーが設定されていない場合
        """
        provider_config = config.llm.providers.get(provider)
        if provider_config is None:
            raise ConfigError(
                f"未対応のLLMプロバイダです: {provider}"
            )

        env_var = provider_config.api_key_env
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ConfigError(
                f"APIキーが設定されていません。"
                f"環境変数 {env_var} を設定してください"
            )

        return api_key
