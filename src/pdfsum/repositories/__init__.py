"""データレイヤー (Repository パターン)"""

from pdfsum.repositories.base import SummaryRepository
from pdfsum.repositories.sqlite import SummaryReader

__all__ = [
    "SummaryRepository",
    "SummaryReader",
]
