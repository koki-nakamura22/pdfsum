"""argparse 定義・メインCLI (digestkit ベースの薄い再実装)。

ideas docs (motif-3-llm-content-digest) の Phase 1 工程
「既存 pdfsum を digestkit ベースで再実装」に従い、本モジュールは
digestkit のパイプラインをそのまま叩く薄いラッパーになっている。
保存先 SQLite のスキーマは digestkit ``SQLiteSink`` の ``digests`` テーブル
(item_id / summary / tokens_in / tokens_out / latency_ms / model / created_at)。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digestkit import Digester, Item, content_sha256_key
from digestkit.dedup import default_seen_store_path
from digestkit.extractors import PDFExtractor
from digestkit.sinks import SQLiteSink
from digestkit.sources import LocalDirectorySource
from digestkit.summarizers import ChunkedLLMSummarizer

from pdfsum import __version__
from pdfsum.cli import display
from pdfsum.config.manager import Config, ConfigManager
from pdfsum.errors import ConfigError, PdfsumError

if TYPE_CHECKING:
    from digestkit import RunResult

# pdfsum 設定の provider 名 → digestkit (litellm) の provider 名
_PROVIDER_TO_LITELLM: dict[str, str] = {
    "gemini": "gemini",
    "claude": "anthropic",
    "openai": "openai",
}

# litellm が参照する API キー環境変数
_LITELLM_ENV_VAR: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_DEFAULT_PROMPT = "以下のドキュメントを日本語で簡潔に要約してください。\n\n{text}"
_DIGESTER_CLASS_NAME = "PdfsumDigester"


def _resolve_db_path(config: Config, override: str | None) -> Path:
    """digestkit ``SQLiteSink`` 用の DB パスを解決する。

    既存 pdfsum は ``[database].path`` (デフォルト ``user_data_dir/summaries.db``)
    を使っていたが、digestkit 化に伴いスキーマが変わるため pdfsum 名義の DB を
    引き続き使う (旧データとは別テーブルになる前提)。
    """
    if override is not None:
        return Path(override).expanduser()
    return Path(config.database.path).expanduser()


def _build_digester(
    source_path: Path,
    *,
    glob: str,
    db_path: Path,
    config: Config,
    chunk_size: int | None = None,
    chunk_overlap: int = 0,
) -> Digester:
    """pdfsum 設定から digestkit Digester を組み立てる。"""
    provider = config.llm.provider
    _mapped = _PROVIDER_TO_LITELLM.get(provider)
    if _mapped is None:
        raise ConfigError(f"digestkit に未対応のプロバイダです: {provider}")
    litellm_provider: str = _mapped

    api_key = ConfigManager().get_api_key(config, provider)

    # litellm はプロバイダ標準名の環境変数を参照するため、pdfsum 設定で
    # 解決したキーをその変数名へ正規化して流し込む。
    os.environ[_LITELLM_ENV_VAR[litellm_provider]] = api_key

    # digestkit のビルトイン 3 段階プロンプトを opt-in. extra_instructions が
    # あれば全段階の先頭に prepend する.
    base_prompts = ChunkedLLMSummarizer.DEFAULT_PROMPTS
    if config.summary.extra_instructions:
        prefix = f"{config.summary.extra_instructions}\n\n"
        prompts = {key: prefix + tmpl for key, tmpl in base_prompts.items()}
    else:
        prompts = dict(base_prompts)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 長文 PDF (論文 / 書籍章) はモデル上限を超えるため Chunked を使う.
    # 上限内に収まる短文は ChunkedLLMSummarizer 内で単発呼び出しに自動 fallback する.
    class PdfsumDigester(Digester):
        source = LocalDirectorySource(source_path, glob=glob)
        extractor = PDFExtractor()
        summarizer = ChunkedLLMSummarizer(
            provider=litellm_provider,
            model=config.llm.model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            prompts=prompts,
            default_length=config.summary.default_length or "standard",
        )
        sink = SQLiteSink(db_path)
        # Issue #12 / inboxkit#21: PDF 内容の SHA-256 を dedup キーにする.
        # 既定の Item.id (絶対パス) ベースだと、同一内容の別パスが再要約され、
        # 同一パスの内容差し替え時に再要約されない. content_sha256_key は両方を解決.
        dedup_key = staticmethod(content_sha256_key)

    return PdfsumDigester()


def _seen_store_path() -> Path:
    return default_seen_store_path(_DIGESTER_CLASS_NAME)


def _select_rows(
    db_path: Path,
    *,
    where: str = "",
    params: tuple[Any, ...] = (),
    order: str = "ORDER BY created_at DESC",
) -> list[dict[str, Any]]:
    """digestkit が書いた ``digests`` テーブルを読む。"""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT rowid, * FROM digests"
        if where:
            sql += f" WHERE {where}"
        sql += f" {order}"
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table: digests" in str(exc):
            # テーブル未作成 = まだ summarize 未実行
            return []
        raise PdfsumError(f"SQLite 読み取りに失敗しました: {exc}") from exc
    finally:
        conn.close()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _resolve_short_id(db_path: Path, short_id: str) -> dict[str, Any]:
    """item_id の末尾 (basename) で 1 件を一意に特定する。

    digestkit の ``Item.id`` は絶対パス文字列。UUID ではないため、ユーザー
    入力としてはファイル名 (basename) もしくはパスの substring を受け付ける。
    """
    rows = _select_rows(
        db_path,
        where=r"item_id LIKE ? ESCAPE '\'",
        params=(f"%{_escape_like(short_id)}%",),
    )
    if not rows:
        raise PdfsumError(f"要約が見つかりません: {short_id}")
    if len({r["item_id"] for r in rows}) > 1:
        raise PdfsumError(
            f"'{short_id}' に複数の要約が一致しました。"
            f"より具体的なパスを指定してください"
        )
    return rows[0]


def _delete_seen_item(item_id: str) -> None:
    """SeenStore から該当エントリを削除する.

    PdfsumDigester は dedup キーに ``content_sha256_key`` を使うため、SeenStore に
    格納されているのは ``sha256:<hex>`` であって ``item_id`` (絶対パス) ではない.
    元ファイルが残っていれば再ハッシュして削除し、消えていれば path フォールバックで
    旧形式 (path ベース) のキーも掃除する.
    """
    seen_db_path = _seen_store_path()
    if not seen_db_path.exists():
        return

    candidate_keys: list[str] = [item_id]  # 旧 path ベース key の掃除も兼ねる
    pdf_path = Path(item_id)
    if pdf_path.is_file():
        try:
            sha_key = content_sha256_key(Item(id=item_id, payload=pdf_path))
            candidate_keys.append(sha_key)
        except OSError:
            # 読めなければ skip (path ベース掃除のみ実施)
            pass

    conn = sqlite3.connect(seen_db_path)
    try:
        with conn:
            placeholders = ",".join("?" for _ in candidate_keys)
            conn.execute(
                f"DELETE FROM seen_items WHERE item_id IN ({placeholders})",
                tuple(candidate_keys),
            )
    except sqlite3.OperationalError as exc:
        if "no such table: seen_items" not in str(exc):
            raise PdfsumError(f"SeenStore の更新に失敗しました: {exc}") from exc
    except sqlite3.Error as exc:
        raise PdfsumError(f"SeenStore の更新に失敗しました: {exc}") from exc
    finally:
        conn.close()


def _print_run_result(result: RunResult) -> int:
    print(
        f"完了: success={result.success} skipped={result.skipped} "
        f"failures={len(result.failures)}"
    )
    for failure in result.failures:
        display.print_error(f"  - {failure.item.id} [{failure.stage}]: {failure.error}")
    return 0 if not result.failures else 1


def cmd_summarize(args: argparse.Namespace) -> int:
    """指定パス (PDF または PDF を含むディレクトリ) を要約する。"""
    target = Path(args.path).expanduser()
    if not target.exists():
        raise PdfsumError(f"パスが存在しません: {target}")

    if target.is_file():
        source_dir = target.parent
        glob = target.name
    else:
        source_dir = target
        glob = args.glob

    config = ConfigManager().load()
    db_path = _resolve_db_path(config, args.db_path)
    digester = _build_digester(
        source_dir,
        glob=glob,
        db_path=db_path,
        config=config,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    result = digester.run(limit=args.limit, dry_run=args.dry_run, length=args.length)
    return _print_run_result(result)


def cmd_list(args: argparse.Namespace) -> int:
    """保存済み要約を一覧表示する。"""
    config = ConfigManager().load()
    db_path = _resolve_db_path(config, args.db_path)
    rows = _select_rows(db_path)
    display.print_digest_list(rows, full_id=args.full_id)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """指定 ID (パス末尾の部分一致) の要約詳細を表示する。"""
    config = ConfigManager().load()
    db_path = _resolve_db_path(config, args.db_path)
    row = _resolve_short_id(db_path, args.summary_id)
    display.print_digest_detail(row)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """指定 ID に紐づく要約を全削除する (item_id 一致全行)。"""
    config = ConfigManager().load()
    db_path = _resolve_db_path(config, args.db_path)
    row = _resolve_short_id(db_path, args.summary_id)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM digests WHERE item_id = ?", (row["item_id"],))
    except sqlite3.Error as exc:
        raise PdfsumError(f"SQLite 書き込みに失敗しました: {exc}") from exc
    finally:
        conn.close()
    _delete_seen_item(row["item_id"])
    display.print_success(f"要約を削除しました: {row['item_id']}")
    return 0


def _add_db_path_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite 出力先 (未指定時は config.toml の database.path)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfsum",
        description="PDFドキュメント要約CLIツール (digestkit ベース)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pdfsum {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="PDF ファイルまたはディレクトリ配下の PDF を要約する",
    )
    summarize_parser.add_argument(
        "path",
        help="PDF ファイルパス または PDF を含むディレクトリ",
    )
    summarize_parser.add_argument(
        "--glob",
        default="*.pdf",
        help="ディレクトリ指定時の glob パターン (デフォルト: *.pdf)",
    )
    summarize_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理件数の上限",
    )
    summarize_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="シンク書き込みをスキップする",
    )
    summarize_parser.add_argument(
        "--length",
        choices=["short", "standard", "detailed"],
        default=None,
        help="要約の長さ (未指定時は config.toml の summary.default_length)",
    )
    summarize_parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="ChunkedLLMSummarizer の chunk_size (tokens). "
        "未指定時はモデル上限から自動算出",
    )
    summarize_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=0,
        help="ChunkedLLMSummarizer の chunk_overlap (tokens, デフォルト 0)",
    )
    _add_db_path_arg(summarize_parser)

    list_parser = subparsers.add_parser(
        "list",
        help="保存済み要約の一覧を表示する",
    )
    list_parser.add_argument(
        "--full-id",
        action="store_true",
        default=False,
        help="完全な item_id (絶対パス) を表示する",
    )
    _add_db_path_arg(list_parser)

    show_parser = subparsers.add_parser(
        "show",
        help="保存済み要約の詳細を表示する",
    )
    show_parser.add_argument(
        "summary_id",
        help="要約 ID (item_id のパス末尾またはファイル名の部分一致)",
    )
    _add_db_path_arg(show_parser)

    delete_parser = subparsers.add_parser(
        "delete",
        help="保存済み要約を削除する",
    )
    delete_parser.add_argument(
        "summary_id",
        help="要約 ID (item_id のパス末尾またはファイル名の部分一致)",
    )
    _add_db_path_arg(delete_parser)

    return parser


def main(args: list[str] | None = None) -> int:
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
