"""公開API (create_service) のテスト"""

from unittest.mock import MagicMock, patch

import pytest

from pdfsum import (
    ConfigError,
    SummarizeService,
    create_service,
)
from pdfsum.config.manager import (
    Config,
    DatabaseConfig,
    LLMConfig,
    SummaryConfig,
)


class TestCreateServiceWithConfig:
    """config.toml連携の正常系テスト"""

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    @patch("pdfsum.config.manager.ConfigManager")
    def test_no_args_uses_config_toml(
        self,
        mock_config_manager_cls: MagicMock,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        """引数なしでconfig.tomlの設定を使用する"""
        mock_config = Config(
            llm=LLMConfig(provider="gemini", model="gemini-2.5-flash"),
            summary=SummaryConfig(),
            database=DatabaseConfig(path="/tmp/test.db"),
        )
        mock_manager = MagicMock()
        mock_manager.load.return_value = mock_config
        mock_manager.get_api_key.return_value = "test-api-key"
        mock_config_manager_cls.return_value = mock_manager

        mock_engine = MagicMock()
        mock_factory_create.return_value = mock_engine

        service = create_service()

        assert isinstance(service, SummarizeService)
        mock_manager.load.assert_called_once()
        mock_manager.get_api_key.assert_called_once_with(mock_config, "gemini")
        mock_factory_create.assert_called_once_with(
            "gemini", "test-api-key", "gemini-2.5-flash", mock_config.summary
        )


class TestCreateServiceWithProvider:
    """provider+api_key明示指定の正常系テスト"""

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_provider_and_api_key(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        """provider+api_key指定で直接構築"""
        mock_engine = MagicMock()
        mock_factory_create.return_value = mock_engine

        service = create_service(provider="claude", api_key="my-key")

        assert isinstance(service, SummarizeService)
        mock_factory_create.assert_called_once()
        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "claude"
        assert call_args[0][1] == "my-key"
        assert call_args[0][2] == "claude-sonnet-4-20250514"

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_env_var_fallback(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """api_key未指定時に環境変数からフォールバック"""
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        mock_factory_create.return_value = MagicMock()

        service = create_service(provider="gemini")

        assert isinstance(service, SummarizeService)
        call_args = mock_factory_create.call_args
        assert call_args[0][1] == "env-key"

    def test_no_api_key_no_env_raises_config_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """api_key未指定・環境変数なしでConfigError"""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ConfigError, match="APIキーが設定されていません"):
            create_service(provider="gemini")

    def test_unsupported_provider_raises_config_error(self) -> None:
        """未対応プロバイダでConfigError"""
        with pytest.raises(ConfigError, match="未対応のLLMプロバイダです"):
            create_service(provider="unknown")


class TestCreateServiceDefaultModel:
    """デフォルトモデル選択のテスト"""

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_default_model_gemini(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(provider="gemini", api_key="key")
        assert mock_factory_create.call_args[0][2] == "gemini-2.5-flash"

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_default_model_claude(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(provider="claude", api_key="key")
        assert mock_factory_create.call_args[0][2] == "claude-sonnet-4-20250514"

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_default_model_openai(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(provider="openai", api_key="key")
        assert mock_factory_create.call_args[0][2] == "gpt-4o"

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_custom_model_overrides_default(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(provider="gemini", api_key="key", model="gemini-2.5-pro")
        assert mock_factory_create.call_args[0][2] == "gemini-2.5-pro"


class TestCreateServiceOptions:
    """オプション引数のテスト"""

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_custom_db_path(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(provider="gemini", api_key="key", db_path="/tmp/custom.db")
        mock_repo_cls.assert_called_once_with("/tmp/custom.db")

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    def test_extra_instructions(
        self,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        mock_factory_create.return_value = MagicMock()
        create_service(
            provider="gemini",
            api_key="key",
            extra_instructions="日本語で要約してください",
        )
        call_args = mock_factory_create.call_args
        summary_config = call_args[0][3]
        assert summary_config.extra_instructions == "日本語で要約してください"

    @patch("pdfsum.repositories.sqlite.SQLiteSummaryRepository")
    @patch("pdfsum.extractors.pdf_extractor.PDFExtractor")
    @patch("pdfsum.engines.factory.SummarizerFactory.create")
    @patch("pdfsum.config.manager.ConfigManager")
    def test_extra_instructions_with_config(
        self,
        mock_config_manager_cls: MagicMock,
        mock_factory_create: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_repo_cls: MagicMock,
    ) -> None:
        """config.toml使用時にextra_instructionsを上書き"""
        mock_config = Config(
            llm=LLMConfig(provider="gemini", model="gemini-2.5-flash"),
            summary=SummaryConfig(extra_instructions="元の指示"),
            database=DatabaseConfig(path="/tmp/test.db"),
        )
        mock_manager = MagicMock()
        mock_manager.load.return_value = mock_config
        mock_manager.get_api_key.return_value = "test-key"
        mock_config_manager_cls.return_value = mock_manager
        mock_factory_create.return_value = MagicMock()

        create_service(extra_instructions="上書き指示")

        call_args = mock_factory_create.call_args
        summary_config = call_args[0][3]
        assert summary_config.extra_instructions == "上書き指示"


class TestAllExports:
    """__all__の全名前がインポート可能かテスト"""

    def test_all_names_importable(self) -> None:
        import pdfsum

        for name in pdfsum.__all__:
            assert hasattr(pdfsum, name), f"{name} is not importable from pdfsum"

    def test_all_contains_expected_names(self) -> None:
        import pdfsum

        expected = {
            "create_service",
            "SummarizeService",
            "Summary",
            "PdfsumError",
            "ConfigError",
            "ExtractionError",
            "SummarizationError",
        }
        assert set(pdfsum.__all__) == expected
