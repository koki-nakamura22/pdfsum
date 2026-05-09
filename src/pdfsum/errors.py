"""pdfsum 例外。

旧 ``pdfsum.models.summary`` から移設 (digestkit 化に伴い models/ を廃止)。
"""

from __future__ import annotations


class PdfsumError(Exception):
    """pdfsum 全般の base 例外。"""


class ConfigError(PdfsumError):
    """設定ファイル / API キー解決の失敗。"""
