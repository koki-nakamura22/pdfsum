"""出力フォーマット・プログレス表示"""

import sys

from pdfsum.models.summary import Summary

SEPARATOR = "━" * 40


def print_summary_result(summary: Summary) -> None:
    """要約結果を表示する。

    Args:
        summary: 表示する要約オブジェクト
    """
    print(f"\n📄 {summary.file_name} ({summary.page_count}ページ)")
    print(SEPARATOR)
    print()
    print(summary.summary_text)
    print()
    print(SEPARATOR)
    print(
        f"モデル: {summary.model_name} | "
        f"要約ID: {summary.id}"
    )


def print_summary_list(
    summaries: list[Summary], full_id: bool = False
) -> None:
    """要約一覧をテーブル形式で表示する。

    Args:
        summaries: 表示する要約のリスト
        full_id: Trueの場合、完全UUIDを表示する
    """
    if not summaries:
        print("保存済みの要約はありません。")
        return

    if full_id:
        id_header = "ID"
        id_width = 36
    else:
        id_header = "ID"
        id_width = 8

    header = (
        f"{id_header:<{id_width}}  "
        f"{'ファイル名':<24}  "
        f"{'ページ':>6}  "
        f"{'長さ':<8}  "
        f"{'作成日時':<16}"
    )
    separator = (
        f"{'─' * id_width}  "
        f"{'─' * 24}  "
        f"{'─' * 6}  "
        f"{'─' * 8}  "
        f"{'─' * 16}"
    )

    print(header)
    print(separator)

    for s in summaries:
        display_id = s.id if full_id else s.id[:8]
        file_name = s.file_name
        if len(file_name) > 24:
            file_name = file_name[:21] + "..."
        created = s.created_at.strftime("%Y-%m-%d %H:%M")

        print(
            f"{display_id:<{id_width}}  "
            f"{file_name:<24}  "
            f"{s.page_count:>6}  "
            f"{s.summary_length:<8}  "
            f"{created:<16}"
        )


def print_summary_detail(summary: Summary) -> None:
    """要約の詳細を表示する。

    Args:
        summary: 表示する要約オブジェクト
    """
    print(f"\n要約ID: {summary.id}")
    print(f"ファイル: {summary.file_name}")
    print(f"パス: {summary.pdf_path}")
    print(f"ページ数: {summary.page_count}")
    print(f"要約長: {summary.summary_length}")
    print(f"モデル: {summary.model_name}")
    print(
        f"作成日時: "
        f"{summary.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print()
    print(SEPARATOR)
    print()
    print(summary.summary_text)
    print()
    print(SEPARATOR)


def print_progress(step: int, total: int, message: str) -> None:
    """プログレス表示。

    Args:
        step: 現在のステップ番号
        total: 総ステップ数
        message: 表示メッセージ
    """
    print(f"[{step}/{total}] {message}", flush=True)


def print_error(message: str) -> None:
    """エラーメッセージを表示する。

    Args:
        message: エラーメッセージ
    """
    print(f"エラー: {message}", file=sys.stderr)


def print_success(message: str) -> None:
    """成功メッセージを表示する。

    Args:
        message: 成功メッセージ
    """
    print(message)
