"""digest_runner.py のユニットテスト (digestkit ドッグフーディング)"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pdfsum.config.manager import Config, LLMConfig, SummaryConfig
from pdfsum.digest_runner import build_digester, run_digest
from pdfsum.models.summary import ConfigError


def _make_config(provider: str = "claude", model: str = "claude-haiku-4-5") -> Config:
    return Config(
        llm=LLMConfig(provider=provider, model=model),
        summary=SummaryConfig(),
    )


class TestBuildDigester:
    def test_build_with_claude(self, tmp_path: Path) -> None:
        cfg = _make_config(provider="claude")
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            digester = build_digester(
                tmp_path, db_path=tmp_path / "out.db", config=cfg
            )

        # Digester に必要属性が揃っていること
        assert hasattr(digester, "source")
        assert hasattr(digester, "extractor")
        assert hasattr(digester, "summarizer")
        assert hasattr(digester, "sink")

    def test_build_with_gemini(self, tmp_path: Path) -> None:
        cfg = _make_config(provider="gemini", model="gemini-2.5-flash")
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
            digester = build_digester(
                tmp_path, db_path=tmp_path / "out.db", config=cfg
            )
        assert digester.summarizer is not None

    def test_unsupported_provider_raises(self, tmp_path: Path) -> None:
        cfg = _make_config(provider="bedrock")
        with pytest.raises(ConfigError):
            build_digester(tmp_path, db_path=tmp_path / "out.db", config=cfg)


class TestRunDigest:
    def test_dry_run_on_empty_directory(self, tmp_path: Path) -> None:
        """空ディレクトリならsuccess=0, failures=0で完走する"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch(
                "pdfsum.digest_runner.ConfigManager"
            ) as mock_cm:
                mock_cm.return_value.load.return_value = _make_config()
                mock_cm.return_value.get_api_key.return_value = "test-key"
                result = run_digest(
                    tmp_path,
                    db_path=tmp_path / "out.db",
                    dry_run=True,
                )

        assert result.success == 0
        assert len(result.failures) == 0
