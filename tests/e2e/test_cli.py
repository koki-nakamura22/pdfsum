"""CLI の E2E テスト"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from pdfsum.cli.app import main

from .conftest import FakeLLMSummarizer


class TestSummarizeCli:
    """in-process で main() を呼び、fake_summarizer で LLM 境界をモックする."""

    def test_summarize_creates_db_row(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        tmp_path: Path,
    ) -> None:
        """summarize 成功時に DB へ 1 行書き込まれる"""
        result = main(["summarize", str(sample_pdf)])

        assert result == 0
        conn = sqlite3.connect(str(tmp_path / "pdfsum.db"))
        rows = conn.execute("SELECT * FROM summaries").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_summarize_default_length_is_standard(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        tmp_path: Path,
    ) -> None:
        """--length 未指定時は standard が DB の length 列に書き込まれる"""
        main(["summarize", str(sample_pdf)])

        conn = sqlite3.connect(str(tmp_path / "pdfsum.db"))
        row = conn.execute("SELECT length FROM summaries").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "standard"

    def test_summarize_short_length(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        tmp_path: Path,
    ) -> None:
        """--length short で DB の length 列が short になる"""
        main(["summarize", str(sample_pdf), "--length", "short"])

        conn = sqlite3.connect(str(tmp_path / "pdfsum.db"))
        row = conn.execute("SELECT length FROM summaries").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "short"

    def test_summarize_invalid_pdf_path_returns_nonzero(
        self,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
    ) -> None:
        """存在しないパス指定で終了コードが非ゼロ"""
        result = main(["summarize", "/nonexistent/path/file.pdf"])

        assert result != 0


class TestListCli:
    """list コマンドの in-process 検証."""

    def test_list_empty_db_prints_no_summaries(
        self,
        isolated_env: dict[str, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """空 DB で list 実行すると「保存済みの要約はありません」が stdout に出る"""
        result = main(["list"])

        assert result == 0
        captured = capsys.readouterr()
        assert "保存済みの要約はありません" in captured.out

    def test_list_after_summarize_shows_filename(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """summarize 後の list にファイル名が表示される"""
        main(["summarize", str(sample_pdf)])
        capsys.readouterr()

        result = main(["list"])

        assert result == 0
        captured = capsys.readouterr()
        assert "sample.pdf" in captured.out

    def test_list_full_id_flag(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--full-id で完全 UUID が stdout に表示される"""
        main(["summarize", str(sample_pdf)])
        capsys.readouterr()

        result = main(["list", "--full-id"])

        assert result == 0
        captured = capsys.readouterr()
        assert re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            captured.out,
        )


class TestShowCli:
    """show コマンドの in-process 検証."""

    def _get_row_id(self, tmp_path: Path) -> str:
        conn = sqlite3.connect(str(tmp_path / "pdfsum.db"))
        row_id = conn.execute("SELECT id FROM summaries").fetchone()[0]
        conn.close()
        return str(row_id)

    def test_show_with_full_uuid(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """完全 UUID で show すると詳細が stdout に表示される"""
        main(["summarize", str(sample_pdf)])
        capsys.readouterr()
        row_id = self._get_row_id(tmp_path)

        result = main(["show", row_id])

        assert result == 0
        captured = capsys.readouterr()
        assert "sample.pdf" in captured.out

    def test_show_with_short_id(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """先頭 8 文字の短縮 ID で show すると詳細が表示される"""
        main(["summarize", str(sample_pdf)])
        capsys.readouterr()
        row_id = self._get_row_id(tmp_path)

        result = main(["show", row_id[:8]])

        assert result == 0
        captured = capsys.readouterr()
        assert "sample.pdf" in captured.out

    def test_show_invalid_id_returns_nonzero(
        self,
        isolated_env: dict[str, str],
    ) -> None:
        """無効な ID 形式で終了コードが非ゼロ"""
        result = main(["show", "invalid-id"])

        assert result != 0


class TestDeleteCli:
    """delete コマンドの in-process 検証."""

    def test_delete_removes_row(
        self,
        sample_pdf: Path,
        isolated_env: dict[str, str],
        fake_summarizer: type[FakeLLMSummarizer],
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """delete 後に DB から行が消える"""
        main(["summarize", str(sample_pdf)])
        capsys.readouterr()
        db_path = tmp_path / "pdfsum.db"
        conn = sqlite3.connect(str(db_path))
        row_id = str(conn.execute("SELECT id FROM summaries").fetchone()[0])
        conn.close()

        result = main(["delete", row_id])

        assert result == 0
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM summaries").fetchall()
        conn.close()
        assert len(rows) == 0

    def test_delete_nonexistent_returns_nonzero(
        self,
        isolated_env: dict[str, str],
    ) -> None:
        """存在しない UUID の削除で終了コードが非ゼロ"""
        result = main(["delete", "00000000-0000-0000-0000-000000000000"])

        assert result != 0


class TestSubprocessSmoke:
    """subprocess で __main__ 経路が壊れていないことを確認する煙幕テスト.

    monkeypatch は子プロセスに伝搬しないため、LLM を呼ばないコマンドのみで smoke する。
    """

    def test_list_via_subprocess(
        self,
        isolated_env: dict[str, str],
    ) -> None:
        """subprocess 経由の list が空 DB で正常終了し出力が正しい"""
        proc = subprocess.run(
            [sys.executable, "-m", "pdfsum", "list"],
            capture_output=True,
            text=True,
            env=isolated_env,
            timeout=30,
        )

        assert proc.returncode == 0
        assert "保存済みの要約はありません" in proc.stdout

    def test_no_args_via_subprocess(
        self,
        isolated_env: dict[str, str],
    ) -> None:
        """subprocess 経由でサブコマンド未指定時に終了コード 2 を返す"""
        proc = subprocess.run(
            [sys.executable, "-m", "pdfsum"],
            capture_output=True,
            text=True,
            env=isolated_env,
            timeout=30,
        )

        assert proc.returncode == 2
