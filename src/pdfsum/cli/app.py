"""argparse 定義・メインCLI"""

import argparse
import re
import sys

from pdfsum import __version__
from pdfsum.cli import display
from pdfsum.config.manager import ConfigManager
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
            f"無効なID形式です: {summary_id}"
            f"（UUID v4または先頭8文字の16進数を指定してください）"
        )


def _build_service_for_summarize() -> SummarizeService:
    """summarizeコマンド用のSummarizeServiceを組み立てる"""
    config_manager = ConfigManager()
    config = config_manager.load()
    api_key = config_manager.get_api_key(config, config.llm.provider)
    engine = SummarizerFactory.create(
        config.llm.provider, api_key, config.llm.model
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
