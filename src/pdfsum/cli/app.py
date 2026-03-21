"""argparse 定義・メインCLI"""

import argparse
import re
import sys
from pathlib import Path

from pdfsum import __version__
from pdfsum.cli import display
from pdfsum.config.manager import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_PROVIDER,
    DEFAULT_SUMMARY_LENGTH,
    ConfigManager,
)
from pdfsum.engines.base import SummarizerEngine
from pdfsum.engines.factory import SummarizerFactory
from pdfsum.extractors.pdf_extractor import PDFExtractor
from pdfsum.models.summary import PdfsumError
from pdfsum.repositories.sqlite import SQLiteSummaryRepository
from pdfsum.services.summarize_service import SummarizeService


class _NullEngine(SummarizerEngine):
    """list/show/deleteコマンド用のダミーエンジン。

    要約生成を行わないコマンドでSummarizeServiceを構築するために使用。
    summarize()が呼ばれた場合はエラーを送出する。
    """

    def summarize(self, text: str, length: str) -> str:
        raise PdfsumError("要約エンジンが初期化されていません")

    def get_model_name(self) -> str:
        return ""

    def get_max_input_tokens(self) -> int:
        return 0


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
SHORT_ID_PATTERN = re.compile(r"^[0-9a-f]{8}$")


def _is_full_uuid(value: str) -> bool:
    """完全なUUID v4形式かどうかを判定する"""
    return bool(UUID_PATTERN.match(value))


def _is_short_id(value: str) -> bool:
    """短縮ID（8文字16進数）かどうかを判定する"""
    return bool(SHORT_ID_PATTERN.match(value))


def _validate_id(summary_id: str) -> None:
    """IDの形式を検証する。

    Raises:
        PdfsumError: 無効なID形式の場合
    """
    if not _is_full_uuid(summary_id) and not _is_short_id(summary_id):
        raise PdfsumError(
            f"無効なID形式です: {summary_id} "
            f"（UUID v4または先頭8文字の16進数を指定してください）"
        )


def _build_service_for_summarize() -> SummarizeService:
    """summarizeコマンド用のSummarizeServiceを組み立てる"""
    config_manager = ConfigManager()
    config = config_manager.load()
    api_key = config_manager.get_api_key(config, config.llm.provider)
    engine = SummarizerFactory.create(
        config.llm.provider, api_key, config.llm.model, config.summary
    )
    extractor = PDFExtractor()
    repository = SQLiteSummaryRepository(config.database.path)
    return SummarizeService(extractor, engine, repository)


def _build_service_for_readonly() -> SummarizeService:
    """list/show/deleteコマンド用のSummarizeServiceを組み立てる。

    エンジン生成不要のため、ダミーエンジンで組み立てる。
    APIキー未設定でもlist/show/deleteは動作する。
    """
    config_manager = ConfigManager()
    config = config_manager.load()
    repository = SQLiteSummaryRepository(config.database.path)
    extractor = PDFExtractor()
    engine = _NullEngine()
    return SummarizeService(extractor, engine, repository)


_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4.1-mini",
}

_PROVIDERS = list(_DEFAULT_MODELS.keys())
_LENGTHS = ["short", "standard", "detailed"]


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


def _prompt_text(prompt: str, default: str) -> str:
    """テキストを対話的に入力させる。"""
    value = input(f"{prompt} (デフォルト: {default}): ").strip()
    return value if value else default


def _confirm(prompt: str) -> bool:
    """yes/no確認を対話的に行う。"""
    value = input(f"{prompt} (y/N): ").strip().lower()
    return value in ("y", "yes")


def _generate_config_toml(
    provider: str,
    model: str,
    length: str,
    db_path: str,
) -> str:
    """config.tomlの内容を生成する。"""
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


def cmd_init(args: argparse.Namespace) -> int:
    """config.toml 対話生成コマンド"""
    config_path = Path(DEFAULT_CONFIG_PATH).expanduser()

    if config_path.exists() and not _confirm(
        f"{config_path} は既に存在します。上書きしますか？"
    ):
        print("中止しました。")
        return 0

    provider = _prompt_choice(
        "LLMプロバイダー", _PROVIDERS, DEFAULT_PROVIDER
    )
    default_model = _DEFAULT_MODELS[provider]
    model = _prompt_text("モデル名", default_model)
    length = _prompt_choice(
        "デフォルト要約長", _LENGTHS, DEFAULT_SUMMARY_LENGTH
    )
    db_path = _prompt_text("データベースパス", DEFAULT_DB_PATH)

    content = _generate_config_toml(provider, model, length, db_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")

    display.print_success(f"設定ファイルを作成しました: {config_path}")
    print()
    print("カスタムプロンプトや追加指示を設定する場合は、")
    print(f"  {config_path}")
    print("を直接編集してください。")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    """PDF要約コマンド"""
    display.print_progress(1, 3, "PDFテキスト抽出中...")
    service = _build_service_for_summarize()
    summary = service.summarize(args.pdf_path, args.length)
    display.print_progress(2, 3, "テキスト要約中... 完了")
    display.print_progress(3, 3, "結果を保存中... 完了")
    display.print_summary_result(summary)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """保存済み要約一覧コマンド"""
    service = _build_service_for_readonly()
    summaries = service.list_summaries()
    display.print_summary_list(summaries, full_id=args.full_id)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """保存済み要約表示コマンド"""
    _validate_id(args.summary_id)
    service = _build_service_for_readonly()

    if _is_full_uuid(args.summary_id):
        summary = service.get_summary(args.summary_id)
        if summary is None:
            raise PdfsumError(
                f"要約が見つかりません (ID: {args.summary_id})"
            )
    else:
        summary = service.get_summary_by_prefix(args.summary_id)

    display.print_summary_detail(summary)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """保存済み要約削除コマンド"""
    _validate_id(args.summary_id)
    service = _build_service_for_readonly()

    if _is_full_uuid(args.summary_id):
        result = service.delete_summary(args.summary_id)
        if not result:
            raise PdfsumError(
                f"要約が見つかりません (ID: {args.summary_id})"
            )
    else:
        service.resolve_and_delete(args.summary_id)

    display.print_success("要約を削除しました。")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """argparseパーサーを構築する"""
    parser = argparse.ArgumentParser(
        prog="pdfsum",
        description="PDFドキュメント要約CLIツール",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pdfsum {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # init サブコマンド
    subparsers.add_parser(
        "init",
        help="設定ファイル (config.toml) を対話的に生成する",
    )

    # summarize サブコマンド
    summarize_parser = subparsers.add_parser(
        "summarize",
        help="PDFファイルを要約する",
    )
    summarize_parser.add_argument(
        "pdf_path",
        help="PDFファイルのパス",
    )
    summarize_parser.add_argument(
        "--length",
        choices=["short", "standard", "detailed"],
        default="standard",
        help="要約の長さ（デフォルト: standard）",
    )

    # list サブコマンド
    list_parser = subparsers.add_parser(
        "list",
        help="保存済み要約の一覧を表示する",
    )
    list_parser.add_argument(
        "--full-id",
        action="store_true",
        default=False,
        help="完全なUUID v4を表示する",
    )

    # show サブコマンド
    show_parser = subparsers.add_parser(
        "show",
        help="保存済み要約の詳細を表示する",
    )
    show_parser.add_argument(
        "summary_id",
        help="要約ID（UUID v4または先頭8文字）",
    )

    # delete サブコマンド
    delete_parser = subparsers.add_parser(
        "delete",
        help="保存済み要約を削除する",
    )
    delete_parser.add_argument(
        "summary_id",
        help="要約ID（UUID v4または先頭8文字）",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    """メインエントリポイント。

    Args:
        args: コマンドライン引数。Noneの場合sys.argvを使用

    Returns:
        終了コード（0: 成功, 1: エラー, 2: 引数エラー）
    """
    parser = _build_parser()
    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 2

    commands = {
        "init": cmd_init,
        "summarize": cmd_summarize,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
    }

    handler = commands.get(parsed.command)
    if handler is None:
        parser.print_help()
        return 2

    try:
        return handler(parsed)
    except PdfsumError as e:
        display.print_error(str(e))
        return 1
    except FileNotFoundError as e:
        display.print_error(str(e))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
