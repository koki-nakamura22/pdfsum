"""PDFファイルからのテキスト抽出"""

import hashlib
from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError

from pdfsum.models.summary import ExtractedDocument, ExtractedPage, ExtractionError

HASH_CHUNK_SIZE = 8192


class PDFExtractor:
    """PDFファイルからテキストを抽出し、ハッシュ値を算出する"""

    def extract(self, pdf_path: str) -> ExtractedDocument:
        """PDFからテキストを抽出する。

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            抽出結果のExtractedDocument

        Raises:
            FileNotFoundError: PDFファイルが存在しない場合
            ExtractionError: PDF以外のファイル、解析失敗、テキスト抽出ゼロの場合
        """
        path = Path(pdf_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

        if path.suffix.lower() != ".pdf":
            raise ExtractionError(f"PDF以外のファイルです: {path.suffix}")

        try:
            pdf_bytes = path.read_bytes()
        except OSError as e:
            raise ExtractionError(
                "PDFの読み取りに失敗しました。ファイルが破損しているか、"
                "パスワード保護されている可能性があります"
            ) from e

        try:
            page_list = list(
                PDFPage.get_pages(BytesIO(pdf_bytes), check_extractable=False)
            )
        except PDFPasswordIncorrect as e:
            raise ExtractionError(
                "PDFの読み取りに失敗しました。ファイルが破損しているか、"
                "パスワード保護されている可能性があります"
            ) from e
        except (PDFSyntaxError, Exception) as e:
            raise ExtractionError(
                "PDFの読み取りに失敗しました。ファイルが破損しているか、"
                "パスワード保護されている可能性があります"
            ) from e

        pages: list[ExtractedPage] = []
        for i in range(len(page_list)):
            text = extract_text(BytesIO(pdf_bytes), page_numbers=[i])
            pages.append(ExtractedPage(page_number=i + 1, text=text))

        total_text = "\n".join(p.text for p in pages)

        if not total_text.strip():
            raise ExtractionError(
                "PDFからテキストを抽出できませんでした。画像のみのPDFの可能性があります"
            )

        pdf_hash = self.calculate_hash(str(path))

        return ExtractedDocument(
            file_name=path.name,
            pdf_path=str(path),
            pdf_hash=pdf_hash,
            page_count=len(pages),
            pages=pages,
            total_text=total_text,
        )

    def calculate_hash(self, pdf_path: str) -> str:
        """PDFファイルのSHA-256ハッシュを算出する。

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            64文字の16進数ハッシュ文字列

        Raises:
            ExtractionError: ファイル読み取りに失敗した場合
        """
        try:
            sha256 = hashlib.sha256()
            with open(pdf_path, "rb") as f:
                while True:
                    chunk = f.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    sha256.update(chunk)
            return sha256.hexdigest()
        except OSError as e:
            raise ExtractionError(
                f"PDFファイルのハッシュ算出に失敗しました: {e}"
            ) from e
