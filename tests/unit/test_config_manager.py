"""ConfigManager のユニットテスト"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pdfsum.config.manager import (
    DEFAULT_DB_PATH,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_SUMMARY_LENGTH,
    ConfigManager,
)
from pdfsum.models.summary import ConfigError


class TestConfigManagerLoad:
    """ConfigManager.load() のテスト"""

    def test_load_returns_default_config_when_file_not_exists(
        self, tmp_path: Path
    ) -> None:
        """設定ファイルが存在しない場合デフォルト設定を返す"""
        manager = ConfigManager(str(tmp_path / "nonexistent.toml"))

        config = manager.load()

        assert config.llm.provider == DEFAULT_PROVIDER
        assert config.llm.model == DEFAULT_MODEL
        assert config.summary.default_length == DEFAULT_SUMMARY_LENGTH
        assert config.database.path == str(Path(DEFAULT_DB_PATH).expanduser())

    def test_load_reads_toml_config(self, tmp_path: Path) -> None:
        """TOML設定ファイルを読み込めること"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[llm]\n'
            'provider = "claude"\n'
            'model = "claude-sonnet-4-6"\n'
            "\n"
            "[llm.claude]\n"
            'api_key_env = "MY_CLAUDE_KEY"\n'
            "\n"
            "[summary]\n"
            'default_length = "detailed"\n'
            "\n"
            "[database]\n"
            'path = "/custom/path/db.sqlite"\n'
        )

        manager = ConfigManager(str(config_path))
        config = manager.load()

        assert config.llm.provider == "claude"
        assert config.llm.model == "claude-sonnet-4-6"
        assert config.llm.providers["claude"].api_key_env == "MY_CLAUDE_KEY"
        assert config.summary.default_length == "detailed"
        assert config.database.path == "/custom/path/db.sqlite"

    def test_load_with_partial_config_uses_defaults(
        self, tmp_path: Path
    ) -> None:
        """部分的な設定ファイルの場合、未指定項目はデフォルト値を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[llm]\nprovider = "openai"\n'
        )

        manager = ConfigManager(str(config_path))
        config = manager.load()

        assert config.llm.provider == "openai"
        assert config.llm.model == DEFAULT_MODEL
        assert config.summary.default_length == DEFAULT_SUMMARY_LENGTH

    def test_load_raises_config_error_for_invalid_toml(
        self, tmp_path: Path
    ) -> None:
        """不正なTOMLファイルでConfigErrorを送出する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text("invalid = [toml content")

        manager = ConfigManager(str(config_path))

        with pytest.raises(ConfigError, match="設定ファイルの読み込みに失敗しました"):
            manager.load()

    def test_load_default_provider_configs(self, tmp_path: Path) -> None:
        """デフォルトのプロバイダ設定が正しいこと"""
        manager = ConfigManager(str(tmp_path / "nonexistent.toml"))
        config = manager.load()

        assert config.llm.providers["gemini"].api_key_env == "GEMINI_API_KEY"
        assert config.llm.providers["claude"].api_key_env == "ANTHROPIC_API_KEY"
        assert config.llm.providers["openai"].api_key_env == "OPENAI_API_KEY"


class TestConfigManagerGetApiKey:
    """ConfigManager.get_api_key() のテスト"""

    def test_get_api_key_returns_env_value(self, tmp_path: Path) -> None:
        """環境変数からAPIキーを取得できる"""
        manager = ConfigManager(str(tmp_path / "nonexistent.toml"))
        config = manager.load()

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key-123"}):
            api_key = manager.get_api_key(config, "gemini")

        assert api_key == "test-key-123"

    def test_get_api_key_raises_config_error_when_not_set(
        self, tmp_path: Path
    ) -> None:
        """APIキー未設定時にConfigErrorを送出する"""
        manager = ConfigManager(str(tmp_path / "nonexistent.toml"))
        config = manager.load()

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfigError, match="APIキーが設定されていません"):
                manager.get_api_key(config, "gemini")

    def test_get_api_key_raises_config_error_for_unknown_provider(
        self, tmp_path: Path
    ) -> None:
        """未対応プロバイダでConfigErrorを送出する"""
        manager = ConfigManager(str(tmp_path / "nonexistent.toml"))
        config = manager.load()

        with pytest.raises(ConfigError, match="未対応のLLMプロバイダです"):
            manager.get_api_key(config, "unknown_provider")

    def test_get_api_key_with_custom_env_var(self, tmp_path: Path) -> None:
        """カスタム環境変数名でAPIキーを取得できる"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[llm.gemini]\n"
            'api_key_env = "MY_CUSTOM_KEY"\n'
        )

        manager = ConfigManager(str(config_path))
        config = manager.load()

        with patch.dict("os.environ", {"MY_CUSTOM_KEY": "custom-key-456"}):
            api_key = manager.get_api_key(config, "gemini")

        assert api_key == "custom-key-456"
