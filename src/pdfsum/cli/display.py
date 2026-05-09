"""出力フォーマット (digestkit ``digests`` テーブル行ベース)。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SEPARATOR = "━" * 40


def _basename(item_id: str) -> str:
    return Path(item_id).name


def _short(item_id: str, width: int = 24) -> str:
    name = _basename(item_id)
    return name if len(name) <= width else name[: width - 3] + "..."


def print_digest_list(rows: list[dict[str, Any]], full_id: bool = False) -> None:
    """digestkit ``digests`` 行の一覧をテーブル表示する。"""
    if not rows:
        print("保存済みの要約はありません。")
        return

    id_width = 60 if full_id else 24
    id_header = "item_id" if full_id else "ファイル名"

    header = (
        f"{id_header:<{id_width}}  "
        f"{'モデル':<24}  "
        f"{'tokens(in/out)':>16}  "
        f"{'作成日時':<20}"
    )
    separator = (
        f"{'─' * id_width}  "
        f"{'─' * 24}  "
        f"{'─' * 16}  "
        f"{'─' * 20}"
    )
    print(header)
    print(separator)
    for r in rows:
        item_id = r["item_id"]
        display_id = item_id if full_id else _short(item_id, id_width)
        model = (r.get("model") or "")[:24]
        tokens = f"{r.get('tokens_in', 0)}/{r.get('tokens_out', 0)}"
        created = (r.get("created_at") or "")[:19]
        print(
            f"{display_id:<{id_width}}  "
            f"{model:<24}  "
            f"{tokens:>16}  "
            f"{created:<20}"
        )


def print_digest_detail(row: dict[str, Any]) -> None:
    """digestkit ``digests`` 1 行の詳細を表示する。"""
    print(f"\nitem_id: {row['item_id']}")
    print(f"モデル: {row.get('model') or ''}")
    print(
        f"tokens: in={row.get('tokens_in', 0)} "
        f"out={row.get('tokens_out', 0)} "
        f"latency_ms={row.get('latency_ms', 0)}"
    )
    print(f"作成日時: {row.get('created_at') or ''}")
    print()
    print(SEPARATOR)
    print()
    print(row.get("summary") or "")
    print()
    print(SEPARATOR)


def print_error(message: str) -> None:
    print(f"エラー: {message}", file=sys.stderr)


def print_success(message: str) -> None:
    print(message)
