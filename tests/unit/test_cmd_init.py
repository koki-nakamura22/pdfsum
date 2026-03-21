"""cmd_init のユニットテスト"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from pdfsum.cli.app import (
    _generate_config_toml,
    cmd_init,
)
from pdfsum.config.manager import (
    DEFAULT_DB_PATH,
    DEFAULT_PROVIDER,
    DEFAULT_SUMMARY_LENGTH,
)


class TestGenerateConfigToml:
    """_generate_config_toml のテスト"""

    def test_generates_valid_toml_content(self) -> None:
        """正しいTOML形式の文字列を生成する"""
        result = _generate_config_toml(
            "gemini", "gemini-2.5-flash", "standard", DEFAULT_DB_PATH
        )
        assert '[llm]' in result
        assert 'provider = "gemini"' in result
        assert 'model = "gemini-2.5-flash"' in result
        assert '[summary]' in result
        assert 'default_length = "standard"' in result
        assert '[database]' in result
        assert f'path = "{DEFAULT_DB_PATH}"' in result

    def test_generates_with_claude_provider(self) -> None:
        """claudeプロバイダーで生成できる"""
        result = _generate_config_toml(
            "claude", "claude-sonnet-4-6", "detailed", "/tmp/test.db"
        )
        assert 'provider = "claude"' in result
        assert 'model = "claude-sonnet-4-6"' in result
        assert 'default_length = "detailed"' in result

    def test_includes_commented_custom_prompt_hints(self) -> None:
        """カスタムプロンプトのヒントがコメントとして含まれる"""
        result = _generate_config_toml(
            "gemini", "gemini-2.5-flash", "standard", DEFAULT_DB_PATH
        )
        assert "# extra_instructions" in result
        assert "# prompt_short" in result
        assert "# prompt_standard" in result
        assert "# prompt_detailed" in result


class TestCmdInit:
    """cmd_init のテスト"""

    @pytest.fixture
    def args(self) -> argparse.Namespace:
        return argparse.Namespace()

    def test_creates_config_file(
        self, args: argparse.Namespace, tmp_path: Path
    ) -> None:
        """config.tomlが正しく作成される"""
        config_path = tmp_path / "pdfsum" / "config.toml"
        inputs = iter(["", "", "", ""])

        with (
            patch(
                "pdfsum.cli.app.DEFAULT_CONFIG_PATH",
                str(config_path),
            ),
            patch("builtins.input", lambda _: next(inputs)),
        ):
            result = cmd_init(args)

        assert result == 0
        assert config_path.exists()
        content = config_path.read_text()
        assert f'provider = "{DEFAULT_PROVIDER}"' in content
        assert f'default_length = "{DEFAULT_SUMMARY_LENGTH}"' in content

    def test_creates_parent_directories(
        self, args: argparse.Namespace, tmp_path: Path
    ) -> None:
        """親ディレクトリが存在しない場合に作成される"""
        config_path = tmp_path / "deep" / "nested" / "config.toml"
        inputs = iter(["", "", "", ""])

        with (
            patch(
                "pdfsum.cli.app.DEFAULT_CONFIG_PATH",
                str(config_path),
            ),
            patch("builtins.input", lambda _: next(inputs)),
        ):
            cmd_init(args)

        assert config_path.parent.exists()

    def test_custom_provider_and_model(
        self, args: argparse.Namespace, tmp_path: Path
    ) -> None:
        """カスタムプロバイダーとモデルが反映される"""
        config_path = tmp_path / "config.toml"
        inputs = iter(["openai", "gpt-4o", "short", ""])

        with (
            patch(
                "pdfsum.cli.app.DEFAULT_CONFIG_PATH",
                str(config_path),
            ),
            patch("builtins.input", lambda _: next(inputs)),
        ):
            cmd_init(args)

        content = config_path.read_text()
        assert 'provider = "openai"' in content
        assert 'model = "gpt-4o"' in content
        assert 'default_length = "short"' in content

    def test_aborts_when_overwrite_declined(
        self, args: argparse.Namespace, tmp_path: Path
    ) -> None:
        """上書き確認で拒否すると中止される"""
        config_path = tmp_path / "config.toml"
        config_path.write_text("existing")
        inputs = iter(["n"])

        with (
            patch(
                "pdfsum.cli.app.DEFAULT_CONFIG_PATH",
                str(config_path),
            ),
            patch("builtins.input", lambda _: next(inputs)),
        ):
            result = cmd_init(args)

        assert result == 0
        assert config_path.read_text() == "existing"

    def test_overwrites_when_confirmed(
        self, args: argparse.Namespace, tmp_path: Path
    ) -> None:
        """上書き確認で承認すると上書きされる"""
        config_path = tmp_path / "config.toml"
        config_path.write_text("existing")
        inputs = iter(["y", "", "", "", ""])

        with (
            patch(
                "pdfsum.cli.app.DEFAULT_CONFIG_PATH",
                str(config_path),
            ),
            patch("builtins.input", lambda _: next(inputs)),
        ):
            result = cmd_init(args)

        assert result == 0
        assert config_path.read_text() != "existing"
        assert "[llm]" in config_path.read_text()
