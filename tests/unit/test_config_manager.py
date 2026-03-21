"""ConfigManager のユニットテスト"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pdfsum.config.manager import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_SUMMARY_LENGTH,
    ConfigManager,
    get_default_config_path,
    get_default_db_path,
)
from pdfsum.models.summary import ConfigError


@pytest.fixture
def empty_env(tmp_path: Path) -> str:
    """空の.envファイルを作成して返す"""
    env_file = tmp_path / "test.env"
    env_file.write_text("")
    return str(env_file)


class TestConfigManagerLoad:
    """ConfigManager.load() のテスト"""

    def test_load_returns_default_config_when_file_not_exists(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """設定ファイルが存在しない場合デフォルト設定を返す"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )

        config = manager.load()

        assert config.llm.provider == DEFAULT_PROVIDER
        assert config.llm.model == DEFAULT_MODEL
        assert config.summary.default_length == DEFAULT_SUMMARY_LENGTH
        assert config.database.path == get_default_db_path()

    def test_load_reads_toml_config(
        self, tmp_path: Path, empty_env: str
    ) -> None:
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

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.llm.provider == "claude"
        assert config.llm.model == "claude-sonnet-4-6"
        assert config.llm.providers["claude"].api_key_env == "MY_CLAUDE_KEY"
        assert config.summary.default_length == "detailed"
        assert config.database.path == "/custom/path/db.sqlite"

    def test_load_with_partial_config_uses_defaults(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """部分的な設定ファイルの場合、未指定項目はデフォルト値を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[llm]\nprovider = "openai"\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.llm.provider == "openai"
        assert config.llm.model == DEFAULT_MODEL
        assert config.summary.default_length == DEFAULT_SUMMARY_LENGTH

    def test_load_raises_config_error_for_invalid_toml(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """不正なTOMLファイルでConfigErrorを送出する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text("invalid = [toml content")

        manager = ConfigManager(str(config_path), env_path=empty_env)

        with pytest.raises(ConfigError, match="設定ファイルの読み込みに失敗しました"):
            manager.load()

    def test_load_default_provider_configs(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """デフォルトのプロバイダ設定が正しいこと"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )
        config = manager.load()

        assert config.llm.providers["gemini"].api_key_env == "GEMINI_API_KEY"
        assert config.llm.providers["claude"].api_key_env == "ANTHROPIC_API_KEY"
        assert config.llm.providers["openai"].api_key_env == "OPENAI_API_KEY"

    def test_load_default_summary_prompt_fields(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """デフォルトではプロンプト関連フィールドが空文字であること"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )
        config = manager.load()

        assert config.summary.extra_instructions == ""
        assert config.summary.prompt_short == ""
        assert config.summary.prompt_standard == ""
        assert config.summary.prompt_detailed == ""

    def test_load_reads_custom_prompt_config(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """カスタムプロンプト設定を読み込めること"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[summary]\n'
            'extra_instructions = "目次は除外してください。"\n'
            'prompt_short = "短く要約して。"\n'
            'prompt_standard = "標準的に要約して。"\n'
            'prompt_detailed = "詳細に要約して。"\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.summary.extra_instructions == "目次は除外してください。"
        assert config.summary.prompt_short == "短く要約して。"
        assert config.summary.prompt_standard == "標準的に要約して。"
        assert config.summary.prompt_detailed == "詳細に要約して。"

    def test_load_reads_multiline_prompt(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """TOML三重引用符の複数行プロンプトを読み込めること"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[summary]\n'
            'prompt_standard = """\n'
            '以下のテキストを要約してください。\n'
            '箇条書きで整理すること。\n'
            '"""\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert "以下のテキストを要約してください。" in config.summary.prompt_standard
        assert "箇条書きで整理すること。" in config.summary.prompt_standard


class TestConfigManagerLoadTypeGuards:
    """ConfigManager.load() の型ガード分岐テスト"""

    def test_non_dict_llm_section_uses_defaults(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """[llm]が非dict値の場合デフォルト設定を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text('llm = "invalid"\n')

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.llm.provider == DEFAULT_PROVIDER
        assert config.llm.model == DEFAULT_MODEL

    def test_non_dict_summary_section_uses_defaults(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """[summary]が非dict値の場合デフォルト設定を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text('summary = "invalid"\n')

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.summary.default_length == DEFAULT_SUMMARY_LENGTH

    def test_non_dict_database_section_uses_defaults(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """[database]が非dict値の場合デフォルト設定を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text('database = "invalid"\n')

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.database.path == get_default_db_path()

    def test_non_dict_provider_config_uses_default_env_var(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """プロバイダ設定が非dict値の場合デフォルト環境変数名を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[llm]\ngemini = "not-a-dict"\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.llm.providers["gemini"].api_key_env == "GEMINI_API_KEY"

    def test_non_string_api_key_env_uses_default(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """api_key_envが非文字列の場合デフォルト環境変数名を使用する"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[llm.gemini]\napi_key_env = 42\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        assert config.llm.providers["gemini"].api_key_env == "GEMINI_API_KEY"


class TestConfigManagerEnvPath:
    """ConfigManager のenv_path解決テスト"""

    def test_loads_env_file_from_specified_path(
        self, tmp_path: Path
    ) -> None:
        """指定した.envファイルから環境変数を読み込む"""
        env_file = tmp_path / "custom.env"
        env_file.write_text("TEST_PDFSUM_KEY=from-env-file\n")

        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=str(env_file)
        )
        manager.load()

        import os
        assert os.environ.get("TEST_PDFSUM_KEY") == "from-env-file"
        # クリーンアップ
        os.environ.pop("TEST_PDFSUM_KEY", None)

    def test_uses_pdfsum_env_path_env_var(self, tmp_path: Path) -> None:
        """PDFSUM_ENV_PATH環境変数で.envファイルパスを指定できる"""
        env_file = tmp_path / "env_var.env"
        env_file.write_text("TEST_PDFSUM_ENV_VAR=from-env-var\n")

        with patch.dict(
            "os.environ", {"PDFSUM_ENV_PATH": str(env_file)}
        ):
            manager = ConfigManager(str(tmp_path / "nonexistent.toml"))
            manager.load()
            import os
            assert os.environ.get("TEST_PDFSUM_ENV_VAR") == "from-env-var"

    def test_arg_takes_precedence_over_env_var_for_env_path(
        self, tmp_path: Path
    ) -> None:
        """env_path引数はPDFSUM_ENV_PATH環境変数より優先される"""
        arg_env = tmp_path / "arg.env"
        arg_env.write_text("TEST_PDFSUM_SOURCE=arg\n")
        env_var_env = tmp_path / "envvar.env"
        env_var_env.write_text("TEST_PDFSUM_SOURCE=envvar\n")

        with patch.dict(
            "os.environ", {"PDFSUM_ENV_PATH": str(env_var_env)}
        ):
            manager = ConfigManager(
                str(tmp_path / "nonexistent.toml"),
                env_path=str(arg_env),
            )
            manager.load()
            import os
            assert os.environ.get("TEST_PDFSUM_SOURCE") == "arg"


class TestConfigManagerConfigPath:
    """ConfigManager のconfig_path解決テスト"""

    def test_uses_env_var_when_no_arg_given(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """引数なしの場合、環境変数PDFSUM_CONFIG_PATHを使用する"""
        config_path = tmp_path / "custom_config.toml"
        config_path.write_text(
            '[llm]\nprovider = "openai"\n'
        )

        with patch.dict(
            "os.environ",
            {"PDFSUM_CONFIG_PATH": str(config_path)},
        ):
            manager = ConfigManager(env_path=empty_env)
            config = manager.load()

        assert config.llm.provider == "openai"

    def test_uses_default_path_when_no_env_var(
        self, empty_env: str
    ) -> None:
        """環境変数も引数もない場合、デフォルトパスを使用する"""
        with patch.dict(
            "os.environ", {}, clear=True
        ):
            manager = ConfigManager(env_path=empty_env)

        assert manager._config_path == Path(get_default_config_path())

    def test_arg_takes_precedence_over_env_var(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """引数指定時は環境変数より優先される"""
        arg_config = tmp_path / "arg_config.toml"
        arg_config.write_text(
            '[llm]\nprovider = "claude"\n'
        )
        env_config = tmp_path / "env_config.toml"
        env_config.write_text(
            '[llm]\nprovider = "openai"\n'
        )

        with patch.dict(
            "os.environ", {"PDFSUM_CONFIG_PATH": str(env_config)}
        ):
            manager = ConfigManager(str(arg_config), env_path=empty_env)
            config = manager.load()

        assert config.llm.provider == "claude"


class TestConfigManagerGetApiKey:
    """ConfigManager.get_api_key() のテスト"""

    def test_get_api_key_returns_env_value(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """環境変数からAPIキーを取得できる"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )
        config = manager.load()

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key-123"}):
            api_key = manager.get_api_key(config, "gemini")

        assert api_key == "test-key-123"

    def test_get_api_key_raises_config_error_when_not_set(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """APIキー未設定時にConfigErrorを送出する"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )
        config = manager.load()

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfigError, match="APIキーが設定されていません"):
                manager.get_api_key(config, "gemini")

    def test_get_api_key_raises_config_error_for_unknown_provider(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """未対応プロバイダでConfigErrorを送出する"""
        manager = ConfigManager(
            str(tmp_path / "nonexistent.toml"), env_path=empty_env
        )
        config = manager.load()

        with pytest.raises(ConfigError, match="未対応のLLMプロバイダです"):
            manager.get_api_key(config, "unknown_provider")

    def test_get_api_key_with_custom_env_var(
        self, tmp_path: Path, empty_env: str
    ) -> None:
        """カスタム環境変数名でAPIキーを取得できる"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[llm.gemini]\n"
            'api_key_env = "MY_CUSTOM_KEY"\n'
        )

        manager = ConfigManager(str(config_path), env_path=empty_env)
        config = manager.load()

        with patch.dict("os.environ", {"MY_CUSTOM_KEY": "custom-key-456"}):
            api_key = manager.get_api_key(config, "gemini")

        assert api_key == "custom-key-456"
