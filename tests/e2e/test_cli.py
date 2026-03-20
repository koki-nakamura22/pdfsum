"""CLI の E2E テスト"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def isolated_env(tmp_path: Path) -> dict[str, str]:
    """全E2Eテスト用の分離された環境を提供する。

    一時的なconfig.toml、DB、.envを使い、
    実際の設定ファイルやDBに触れないようにする。
    """
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "config.toml"
    env_path = tmp_path / "test.env"
    config_path.write_text(
        f'[database]\npath = "{db_path}"\n'
    )
    env_path.write_text("")

    env = os.environ.copy()
    env["PDFSUM_CONFIG_PATH"] = str(config_path)
    env["PDFSUM_ENV_PATH"] = str(env_path)
    return env


def _run_pdfsum(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """pdfsum CLIを実行するヘルパー"""
    return subprocess.run(
        [sys.executable, "-m", "pdfsum", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


class TestCLIVersion:
    """--version のテスト"""

    def test_version_displays_version_string(
        self, isolated_env: dict[str, str]
    ) -> None:
        """--version でバージョン文字列が表示される"""
        result = _run_pdfsum("--version", env=isolated_env)
        assert result.returncode == 0
        assert "pdfsum" in result.stdout


class TestCLIHelp:
    """--help のテスト"""

    def test_help_displays_usage(
        self, isolated_env: dict[str, str]
    ) -> None:
        """--help で使い方が表示される"""
        result = _run_pdfsum("--help", env=isolated_env)
        assert result.returncode == 0
        assert "summarize" in result.stdout
        assert "list" in result.stdout
        assert "show" in result.stdout
        assert "delete" in result.stdout


class TestCLIInvalidCommand:
    """不正なコマンドのテスト"""

    def test_no_command_returns_exit_code_2(
        self, isolated_env: dict[str, str]
    ) -> None:
        """サブコマンド未指定で終了コード2"""
        result = _run_pdfsum(env=isolated_env)
        assert result.returncode == 2


class TestCLIListCommand:
    """list コマンドのテスト"""

    def test_list_empty_db(self, isolated_env: dict[str, str]) -> None:
        """空DBでlist実行が正常終了する"""
        result = _run_pdfsum("list", env=isolated_env)
        assert result.returncode == 0
        assert "保存済みの要約はありません" in result.stdout


class TestCLIShowCommand:
    """show コマンドのテスト"""

    def test_show_with_invalid_id_returns_exit_code_1(
        self, isolated_env: dict[str, str]
    ) -> None:
        """無効なID形式で終了コード1"""
        result = _run_pdfsum("show", "invalid-id", env=isolated_env)
        assert result.returncode == 1
        assert "無効なID形式です" in result.stderr


class TestCLIDeleteCommand:
    """delete コマンドのテスト"""

    def test_delete_with_invalid_id_returns_exit_code_1(
        self, isolated_env: dict[str, str]
    ) -> None:
        """無効なID形式で終了コード1"""
        result = _run_pdfsum("delete", "invalid-id", env=isolated_env)
        assert result.returncode == 1
        assert "無効なID形式です" in result.stderr


class TestCLISummarizeCommand:
    """summarize コマンドのテスト"""

    def test_summarize_nonexistent_file_returns_exit_code_1(
        self, isolated_env: dict[str, str]
    ) -> None:
        """存在しないファイル指定で終了コード1"""
        result = _run_pdfsum(
            "summarize", "/nonexistent/file.pdf", env=isolated_env
        )
        assert result.returncode == 1
