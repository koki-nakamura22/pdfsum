"""display の単体テスト (digestkit ``digests`` 行ベース)。"""

from __future__ import annotations

import pytest

from pdfsum.cli import display


def _row(item_id: str, summary: str = "s") -> dict[str, object]:
    return {
        "item_id": item_id,
        "summary": summary,
        "tokens_in": 100,
        "tokens_out": 20,
        "latency_ms": 300,
        "model": "claude-haiku",
        "created_at": "2026-05-09T10:00:00",
    }


def test_print_digest_list_empty(capsys: pytest.CaptureFixture[str]) -> None:
    display.print_digest_list([])
    assert "保存済みの要約はありません" in capsys.readouterr().out


def test_print_digest_list_truncates_basename(
    capsys: pytest.CaptureFixture[str],
) -> None:
    long = "/tmp/" + "x" * 100 + ".pdf"
    display.print_digest_list([_row(long)])
    out = capsys.readouterr().out
    # full path は出さず、末尾 "..." で省略される
    assert long not in out
    assert "..." in out


def test_print_digest_list_full_id(capsys: pytest.CaptureFixture[str]) -> None:
    display.print_digest_list([_row("/abs/path/file.pdf")], full_id=True)
    assert "/abs/path/file.pdf" in capsys.readouterr().out


def test_print_digest_detail(capsys: pytest.CaptureFixture[str]) -> None:
    display.print_digest_detail(_row("/p/a.pdf", summary="hello"))
    out = capsys.readouterr().out
    assert "/p/a.pdf" in out
    assert "hello" in out
    assert "claude-haiku" in out


def test_print_error_goes_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    display.print_error("oops")
    captured = capsys.readouterr()
    assert "oops" in captured.err
    assert captured.out == ""
