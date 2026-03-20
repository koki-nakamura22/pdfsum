"""base.py のユニットテスト"""

import pytest

from pdfsum.config.manager import SummaryConfig
from pdfsum.engines.base import DEFAULT_PROMPTS, get_prompt_for_length
from pdfsum.models.summary import SummarizationError


class TestGetPromptForLength:
    """get_prompt_for_length のテスト"""

    def test_returns_default_prompt_when_no_config(self) -> None:
        """config未指定時はデフォルトプロンプトを返す"""
        for length in ("short", "standard", "detailed"):
            result = get_prompt_for_length(length)
            assert result == DEFAULT_PROMPTS[length]

    def test_returns_default_prompt_when_config_has_no_custom(self) -> None:
        """カスタムプロンプト未設定のconfigでもデフォルトを返す"""
        config = SummaryConfig()
        for length in ("short", "standard", "detailed"):
            result = get_prompt_for_length(length, config)
            assert result == DEFAULT_PROMPTS[length]

    def test_custom_prompt_overrides_default(self) -> None:
        """カスタムプロンプトがデフォルトを上書きする"""
        config = SummaryConfig(prompt_standard="カスタム要約プロンプト")
        result = get_prompt_for_length("standard", config)
        assert result == "カスタム要約プロンプト"

    def test_custom_prompt_only_affects_specified_length(self) -> None:
        """カスタムプロンプトは指定した段階のみ上書きする"""
        config = SummaryConfig(prompt_short="短い要約")
        assert get_prompt_for_length("short", config) == "短い要約"
        assert get_prompt_for_length("standard", config) == DEFAULT_PROMPTS["standard"]
        assert get_prompt_for_length("detailed", config) == DEFAULT_PROMPTS["detailed"]

    def test_extra_instructions_appended_to_default_prompt(self) -> None:
        """extra_instructionsがデフォルトプロンプトの末尾に追記される"""
        config = SummaryConfig(extra_instructions="目次は除外してください。")
        result = get_prompt_for_length("standard", config)
        assert result.startswith(DEFAULT_PROMPTS["standard"])
        assert result.endswith("目次は除外してください。")
        assert "\n\n" in result

    def test_extra_instructions_appended_to_custom_prompt(self) -> None:
        """extra_instructionsがカスタムプロンプトの末尾にも追記される"""
        config = SummaryConfig(
            prompt_standard="カスタム要約",
            extra_instructions="謝辞は除外。",
        )
        result = get_prompt_for_length("standard", config)
        assert result == "カスタム要約\n\n謝辞は除外。"

    def test_extra_instructions_applied_to_all_lengths(self) -> None:
        """extra_instructionsは全段階に適用される"""
        config = SummaryConfig(extra_instructions="参考文献は除外。")
        for length in ("short", "standard", "detailed"):
            result = get_prompt_for_length(length, config)
            assert result.endswith("参考文献は除外。")

    def test_invalid_length_raises_error(self) -> None:
        """無効な要約長でSummarizationErrorを送出する"""
        with pytest.raises(SummarizationError, match="無効な要約長です"):
            get_prompt_for_length("invalid")

    def test_invalid_length_with_config_raises_error(self) -> None:
        """config指定時も無効な要約長でエラーになる"""
        config = SummaryConfig(extra_instructions="テスト")
        with pytest.raises(SummarizationError, match="無効な要約長です"):
            get_prompt_for_length("invalid", config)
