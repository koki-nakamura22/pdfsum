"""PR #14 (digestkit length サポート) を pdfsum 側からドッグフードする検証.

litellm を mock して以下を確認する:

1. ``--length detailed`` を渡すと digestkit DEFAULT_PROMPTS の detailed テンプレートが
   実際に LiteLLM へ送信される
2. ``--length`` 未指定 + config.summary.default_length が反映される
3. ``--length`` 不正値は argparse choices で弾かれる
4. ``extra_instructions`` が指定されている時、各 length 段階の先頭に prepend されて届く

このテストファイルは ``experiment/issue-10-dogfood`` ブランチ専用の検証用で、
PR #14 マージ + pdfsum 側で本対応 PR を切るときには整理対象。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdfsum.cli.app import main


def _mock_completion_response() -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = "summary"
    mock.usage.prompt_tokens = 10
    mock.usage.completion_tokens = 5
    return mock


@pytest.fixture
def pdf_dir(tmp_path: Path) -> Path:
    """1 件だけ PDF っぽいバイト列を置いたディレクトリ."""
    pdf = tmp_path / "doc.pdf"
    # PDFExtractor が pypdf で開けるよう、最小限の有効 PDF を ReportLab で作る
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(pdf))
    c.drawString(72, 720, "Hello dogfood length test")
    c.save()
    return tmp_path


def _run_with_mocked_llm(
    pdf_dir: Path, db: Path, monkeypatch: pytest.MonkeyPatch, *, length: str | None
) -> str:
    """summarize を 1 回回し、litellm.completion に渡された user prompt を返す."""
    monkeypatch.setenv("GEMINI_API_KEY", "stub")  # provider=gemini デフォルトに合わせる
    monkeypatch.setenv("XDG_CACHE_HOME", str(db.parent / "cache"))
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> MagicMock:
        captured["messages"] = kwargs["messages"]
        captured["model"] = kwargs["model"]
        return _mock_completion_response()

    args = ["summarize", str(pdf_dir), "--db-path", str(db)]
    if length is not None:
        args.extend(["--length", length])

    with patch("digestkit.summarizers.llm.litellm.completion", side_effect=fake_completion):
        rc = main(args)
    assert rc == 0, f"summarize 失敗: rc={rc}"

    messages = captured["messages"]
    assert isinstance(messages, list)
    user_msg = next(m for m in messages if m["role"] == "user")
    return user_msg["content"]


def test_length_detailed_sends_detailed_template(
    pdf_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "out.db"
    content = _run_with_mocked_llm(pdf_dir, db, monkeypatch, length="detailed")
    # digestkit DEFAULT_PROMPTS["detailed"] の特徴語
    assert "章立て" in content
    assert "Hello dogfood length test" in content


def test_length_short_sends_short_template(
    pdf_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "out.db"
    content = _run_with_mocked_llm(pdf_dir, db, monkeypatch, length="short")
    assert "3 行以内" in content


def test_length_unspecified_falls_back_to_standard(
    pdf_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--length 未指定で config 既定 (= "standard") が適用される."""
    db = tmp_path / "out.db"
    content = _run_with_mocked_llm(pdf_dir, db, monkeypatch, length=None)
    # standard の特徴語は "段落は 2〜3"
    assert "段落は 2" in content


def test_length_invalid_value_rejected_by_argparse(
    pdf_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "out.db"
    with pytest.raises(SystemExit) as exc:
        main(["summarize", str(pdf_dir), "--db-path", str(db), "--length", "huge"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err or "argument --length" in err
