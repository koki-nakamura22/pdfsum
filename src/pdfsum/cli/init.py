"""config.toml 対話生成"""

from pathlib import Path

from pdfsum.config.manager import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_PROVIDER,
    DEFAULT_PROVIDER_CONFIGS,
    DEFAULT_SUMMARY_LENGTH,
)
from pdfsum.engines.claude import DEFAULT_CLAUDE_MODEL
from pdfsum.engines.gemini import DEFAULT_GEMINI_MODEL
from pdfsum.engines.openai import DEFAULT_OPENAI_MODEL

_DEFAULT_MODELS: dict[str, str] = {
    "gemini": DEFAULT_GEMINI_MODEL,
    "claude": DEFAULT_CLAUDE_MODEL,
    "openai": DEFAULT_OPENAI_MODEL,
}

_PROVIDERS = list(DEFAULT_PROVIDER_CONFIGS.keys())
_LENGTHS = ["short", "standard", "detailed"]


class ConfigInitializer:
    """対話的に config.toml を生成する。"""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        self._config_path = Path(config_path).expanduser()

    def run(self) -> int:
        """対話を実行し config.toml を書き出す。

        Returns:
            終了コード（0: 成功）
        """
        if self._config_path.exists() and not self._confirm(
            f"{self._config_path} は既に存在します。上書きしますか？"
        ):
            print("中止しました。")
            return 0

        provider = self._prompt_choice(
            "LLMプロバイダー", _PROVIDERS, DEFAULT_PROVIDER
        )
        default_model = _DEFAULT_MODELS[provider]
        model = self._prompt_text("モデル名", default_model)
        length = self._prompt_choice(
            "デフォルト要約長", _LENGTHS, DEFAULT_SUMMARY_LENGTH
        )
        db_path = self._prompt_text("データベースパス", DEFAULT_DB_PATH)

        content = self._generate_toml(provider, model, length, db_path)

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(content, encoding="utf-8")

        print(f"設定ファイルを作成しました: {self._config_path}")
        print()
        print("カスタムプロンプトや追加指示を設定する場合は、")
        print(f"  {self._config_path}")
        print("を直接編集してください。")
        return 0

    @staticmethod
    def _generate_toml(
        provider: str,
        model: str,
        length: str,
        db_path: str,
    ) -> str:
        """config.toml の内容を生成する。"""
        return (
            "[llm]\n"
            f'provider = "{provider}"\n'
            f'model = "{model}"\n'
            "\n"
            "[summary]\n"
            f'default_length = "{length}"\n'
            "\n"
            "# 全プロンプト共通の追加指示（任意）\n"
            '# extra_instructions = ""\n'
            "\n"
            "# 各段階のプロンプトを完全に上書き（任意）\n"
            '# prompt_short = "..."\n'
            '# prompt_standard = "..."\n'
            '# prompt_detailed = "..."\n'
            "\n"
            "[database]\n"
            f'path = "{db_path}"\n'
        )

    @staticmethod
    def _prompt_choice(
        prompt: str,
        choices: list[str],
        default: str,
    ) -> str:
        """選択肢を対話的に入力させる。"""
        choices_str = " / ".join(choices)
        while True:
            value = input(
                f"{prompt} ({choices_str}) (デフォルト: {default}): "
            ).strip()
            if not value:
                return default
            if value in choices:
                return value
            print(f"  → {', '.join(choices)} から選択してください。")

    @staticmethod
    def _prompt_text(prompt: str, default: str) -> str:
        """テキストを対話的に入力させる。"""
        value = input(f"{prompt} (デフォルト: {default}): ").strip()
        return value if value else default

    @staticmethod
    def _confirm(prompt: str) -> bool:
        """yes/no 確認を対話的に行う。"""
        value = input(f"{prompt} (y/N): ").strip().lower()
        return value in ("y", "yes")
