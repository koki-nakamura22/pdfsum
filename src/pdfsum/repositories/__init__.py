"""データレイヤー (Repository パターン)"""

from pdfsum.repositories.base import SummaryRepository
from pdfsum.repositories.sqlite import SQLiteSummaryRepository

__all__ = [
    "SummaryRepository",
    "SQLiteSummaryRepository",
]
