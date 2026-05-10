"""データモデル定義.

例外型は ``pdfsum.errors`` へ移管済み (ADR-002 に伴う T008)。
旧 import 経路 (``from pdfsum.models.summary import PdfsumError`` 等)
の後方互換のため、ここから re-export する。新規コードは ``pdfsum.errors``
を直接 import すること。
"""

from dataclasses import dataclass
from datetime import datetime

from pdfsum.errors import (
    ConfigError,
    ExtractionError,
    PdfsumError,
    SummarizationError,
)

__all__ = [
    "ConfigError",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractionError",
    "PdfsumError",
    "Summary",
    "SummarizationError",
]


@dataclass
class ExtractedPage:
    """抽出されたページのテキスト"""

    page_number: int  # ページ番号（1始まり）
    text: str  # 抽出されたテキスト


@dataclass
class ExtractedDocument:
    """PDFから抽出されたテキストデータ"""

    file_name: str  # ファイル名
    pdf_path: str  # ファイルパス
    pdf_hash: str  # SHA-256ハッシュ
    page_count: int  # 総ページ数
    pages: list[ExtractedPage]  # ページごとの抽出結果
    total_text: str  # 全ページ結合テキスト


@dataclass
class Summary:
    """要約結果"""

    id: str  # UUID v4
    pdf_path: str  # 元PDFの絶対パス
    pdf_hash: str  # PDFファイルのSHA-256ハッシュ
    file_name: str  # PDFファイル名
    page_count: int  # PDFの総ページ数
    summary_text: str  # 要約テキスト
    summary_length: str  # "short" | "standard" | "detailed"
    model_name: str  # 使用したLLMモデル名
    created_at: datetime  # 作成日時
