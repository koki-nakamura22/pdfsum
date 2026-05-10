"""argparse 定義・メインCLI"""

from __future__ import annotations

import argparse
import logging
import re
import sys

from digestkit import DigestkitError

from pdfsum import __version__, create_service
from pdfsum.cli import display
from pdfsum.config.manager import ConfigManager
from pdfsum.errors import PdfsumError, exit_code_for, format_digestkit_error
from pdfsum.services.summarize_service import SummarizeService


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


def _build_service_for_write() -> SummarizeService:
    """summarize 用 (LLM 必須)。create_service 経由で公開 API を通る."""
    return create_service()


def _build_service_for_read() -> SummarizeService:
    """list/show/delete 用 (LLM 不要)。API キー未設定でも動かす.

    create_service は LLM 設定を要求するため、読み出し専用は
    SummarizeService(config) を直接呼ぶ。constructor 変更は
    _common.md note に従い許容 (内部結合用シグネチャ).
    """
    config = ConfigManager().load()
    return SummarizeService(config)


def cmd_summarize(args: argparse.Namespace) -> int:
    """PDF要約コマンド"""
    display.print_progress(1, 3, "PDFテキスト抽出中...")
    service = _build_service_for_write()
    summary = service.summarize(args.pdf_path, args.length)
    display.print_progress(2, 3, "テキスト要約中... 完了")
    display.print_progress(3, 3, "結果を保存中... 完了")
    display.print_summary_result(summary)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """保存済み要約一覧コマンド"""
    service = _build_service_for_read()
    summaries = service.list_summaries()
    display.print_summary_list(summaries, full_id=args.full_id)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """保存済み要約表示コマンド"""
    _validate_id(args.summary_id)
    service = _build_service_for_read()

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
    service = _build_service_for_read()

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
    # digestkit が INFO レベルで出力するログ (例: "llm_call_completed") を
    # CLI の出力に混ぜないため WARNING に抑制する。Python ライブラリとして
    # 利用される場合 (create_service / SummarizeService) はロガー設定を
    # 利用者側に委ねたいので、本関数 (CLI エントリ) のみで設定する。
    #
    # digestkit.logging.get_logger は子ロガー (digestkit.summarizers.llm 等) に
    # 直接 setLevel(INFO) するため、親 "digestkit" だけ WARNING にしても
    # 効かない。import 済み (= main() 到達時点) の digestkit 系ロガーを
    # 全て走査して WARNING に上書きする。
    for _name in list(logging.Logger.manager.loggerDict):
        if _name.startswith("digestkit"):
            logging.getLogger(_name).setLevel(logging.WARNING)

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
        return exit_code_for(e)
    except DigestkitError as e:
        display.print_error(format_digestkit_error(e))
        return exit_code_for(e)
    except FileNotFoundError as e:
        display.print_error(str(e))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
