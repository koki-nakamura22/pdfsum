"""CLI (digestkit ベース) のスモークテスト。

実際の LLM 呼び出しを伴う ``summarize`` サブコマンドは外部 API 依存のため
ここでは検証せず (e2e ドッグフーディングで確認)、digestkit が書く
``digests`` テーブルを前提とする ``list`` / ``show`` / ``delete`` の
3 サブコマンド + パース層に絞ってテストする。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from pdfsum.cli.app import _build_parser, main


@pytest.fixture
def populated_db(tmp_path: Path) -> Iterator[Path]:
    """digestkit ``SQLiteSink`` 互換のレコードを投入した DB を返す。"""
    db = tmp_path / "digests.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE digests ("
        "item_id TEXT, summary TEXT, tokens_in INT, tokens_out INT, "
        "latency_ms INT, model TEXT, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO digests VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "/tmp/papers/alpha.pdf",
                "alpha summary",
                100,
                30,
                500,
                "claude-haiku",
                "2026-05-09T10:00:00",
            ),
            (
                "/tmp/papers/beta.pdf",
                "beta summary",
                200,
                40,
                600,
                "claude-haiku",
                "2026-05-09T11:00:00",
            ),
        ],
    )
    conn.commit()
    conn.close()
    yield db


def test_parser_has_four_subcommands() -> None:
    parser = _build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert actions
    choices = set(actions[0].choices or {})
    assert choices == {"summarize", "list", "show", "delete"}


def test_list_empty_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "missing.db"
    rc = main(["list", "--db-path", str(db)])
    assert rc == 0
    assert "保存済みの要約はありません" in capsys.readouterr().out


def test_list_shows_rows(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["list", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha.pdf" in out
    assert "beta.pdf" in out
    # 既定では絶対パスは出さず basename だけ
    assert "/tmp/papers/" not in out


def test_list_full_id(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["list", "--full-id", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/tmp/papers/alpha.pdf" in out


def test_show_resolves_basename(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["show", "alpha", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha summary" in out
    assert "claude-haiku" in out


def test_show_not_found(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["show", "missing", "--db-path", str(populated_db)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "見つかりません" in err


def test_delete_removes_row(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["delete", "alpha", "--db-path", str(populated_db)])
    assert rc == 0
    # 削除メッセージ自体に "alpha" が出るので、ここで一度バッファを切る
    capsys.readouterr()
    rc2 = main(["list", "--db-path", str(populated_db)])
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "alpha.pdf" not in out
    assert "beta.pdf" in out


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 2
    assert "pdfsum" in capsys.readouterr().out
