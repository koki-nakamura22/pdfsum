"""pdfsum - PDFドキュメント要約CLIツール (digestkit ベース)。

ideas docs (motif-3-llm-content-digest) Phase 1 工程 「pdfsum を digestkit
ベースで再実装」に従い、本パッケージは digestkit のパイプラインを叩く CLI
シェルだけを提供する。プログラム的な公開 API は保持していない
(旧 ``create_service`` / ``SummarizeService`` 等は廃止)。
"""

from __future__ import annotations

from importlib.metadata import version as _pkg_version

from pdfsum.errors import ConfigError, PdfsumError

__version__ = _pkg_version("pdfsum")

__all__ = [
    "PdfsumError",
    "ConfigError",
]
