"""E2E テスト用フィクスチャ"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from digestkit.types import Digest, Item
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class FakeLLMSummarizer:
    """digestkit Summarizer Protocol を満たすテスト用フェイク.

    LLM を呼ばずに固定文字列を返す。provider/model/prompts/default_length
    の引数互換を保つため __init__ で全部受け取って保持する。
    """

    DEFAULT_PROMPTS = {"short": "{text}", "standard": "{text}", "detailed": "{text}"}

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        prompts: dict[str, str] | None = None,
        default_length: str | None = None,
        **_: Any,
    ) -> None:
        self.provider = provider
        self.model = model
        self.prompts = prompts or self.DEFAULT_PROMPTS
        self.default_length = default_length

    def summarize(self, text: str, item: Item, *, length: str | None = None) -> Digest:
        used_length = length or self.default_length or "standard"
        return Digest(
            summary=f"[テスト要約 length={used_length}] {text[:30]}...",
            tokens_in=100,
            tokens_out=50,
            latency_ms=1,
            model=self.model,
        )


@pytest.fixture
def fake_summarizer(monkeypatch: pytest.MonkeyPatch) -> type[FakeLLMSummarizer]:
    """pdfsum 側の LLMSummarizer/ChunkedLLMSummarizer シンボルを差し替える.

    digestkit 本体ではなく pdfsum.services.summarize_service モジュールの
    シンボルだけを差し替えることで、digestkit 内部に副作用を出さない。
    """
    monkeypatch.setattr(
        "pdfsum.services.summarize_service.LLMSummarizer", FakeLLMSummarizer
    )
    monkeypatch.setattr(
        "pdfsum.services.summarize_service.ChunkedLLMSummarizer", FakeLLMSummarizer
    )
    return FakeLLMSummarizer


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """テキスト埋め込み済みの簡易 PDF を生成する."""
    pdf_path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.drawString(72, 700, "This is a sample PDF for E2E testing.")
    c.drawString(72, 680, "It contains English text for extraction.")
    c.save()
    return pdf_path


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """設定 / DB / API キー / digestkit キャッシュを当該テスト内に隔離する.

    monkeypatch で PDFSUM_CONFIG_PATH・OPENAI_API_KEY・XDG_CACHE_HOME を
    設定した後の os.environ のコピーを返すため、subprocess テストでも流用できる。
    """
    db_path = tmp_path / "pdfsum.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[llm]\nprovider = "openai"\n\n[database]\npath = "{db_path}"\n'
    )
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("PDFSUM_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    return os.environ.copy()
