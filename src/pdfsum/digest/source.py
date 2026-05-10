"""単一 PDF ファイル用 digestkit Source 実装."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from digestkit.types import Item


class SingleFileSource:
    """単一ファイル → 1 件の Item を yield する digestkit Source.

    digestkit の LocalDirectorySource はディレクトリ前提のため、
    pdfsum summarize <pdf_path> の単一ファイル入力用に提供する。
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def fetch(self) -> Iterable[Item]:
        if not self._path.is_file():
            return
        yield Item(id=str(self._path.resolve()), payload=self._path)
