"""PDFExtractor のユニットテスト"""

from pathlib import Path

import pytest

from pdfsum.extractors.pdf_extractor import PDFExtractor
from pdfsum.models.summary import ExtractionError


class TestPDFExtractorExtract:
    """PDFExtractor.extract() のテスト"""

    def setup_method(self) -> None:
        self.extractor = PDFExtractor()

    def test_extract_english_pdf_returns_extracted_document(
        self, sample_pdf_en: Path
    ) -> None:
        """英語PDFからテキストを正しく抽出できる"""
        result = self.extractor.extract(str(sample_pdf_en))

        assert result.file_name == "sample_en.pdf"
        assert result.page_count == 1
        assert len(result.pages) == 1
        assert "sample PDF document" in result.total_text
        assert result.pages[0].page_number == 1

    def test_extract_japanese_pdf_returns_extracted_document(
        self, sample_pdf_ja: Path
    ) -> None:
        """日本語PDFからテキストを正しく抽出できる"""
        result = self.extractor.extract(str(sample_pdf_ja))

        assert result.file_name == "sample_ja.pdf"
        assert result.page_count == 1
        assert "テスト用のPDFドキュメント" in result.total_text

    def test_extract_multipage_pdf_preserves_page_numbers(
        self, sample_pdf_multipage: Path
    ) -> None:
        """複数ページPDFでページ番号が正しく保持される"""
        result = self.extractor.extract(str(sample_pdf_multipage))

        assert result.page_count == 3
        assert len(result.pages) == 3
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2
        assert result.pages[2].page_number == 3
        assert "Page 1" in result.pages[0].text
        assert "Page 2" in result.pages[1].text
        assert "Page 3" in result.pages[2].text

    def test_extract_returns_correct_pdf_path(self, sample_pdf_en: Path) -> None:
        """抽出結果にPDFの絶対パスが含まれる"""
        result = self.extractor.extract(str(sample_pdf_en))

        assert result.pdf_path == str(sample_pdf_en.resolve())

    def test_extract_returns_valid_hash(self, sample_pdf_en: Path) -> None:
        """抽出結果にSHA-256ハッシュが含まれる"""
        result = self.extractor.extract(str(sample_pdf_en))

        assert len(result.pdf_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.pdf_hash)

    def test_extract_total_text_is_joined_pages(
        self, sample_pdf_multipage: Path
    ) -> None:
        """total_textが全ページのテキストを結合したものである"""
        result = self.extractor.extract(str(sample_pdf_multipage))

        for page in result.pages:
            assert page.text in result.total_text

    def test_extract_nonexistent_file_raises_file_not_found(self) -> None:
        """存在しないファイルでFileNotFoundErrorが発生する"""
        with pytest.raises(FileNotFoundError, match="ファイルが見つかりません"):
            self.extractor.extract("/nonexistent/path/doc.pdf")

    def test_extract_non_pdf_file_raises_extraction_error(
        self, non_pdf_file: Path
    ) -> None:
        """PDF以外のファイルでExtractionErrorが発生する"""
        with pytest.raises(ExtractionError, match="PDF以外のファイルです"):
            self.extractor.extract(str(non_pdf_file))

    def test_extract_empty_pdf_raises_extraction_error(
        self, empty_pdf: Path
    ) -> None:
        """テキストなしPDFでExtractionErrorが発生する"""
        with pytest.raises(ExtractionError, match="テキストを抽出できませんでした"):
            self.extractor.extract(str(empty_pdf))

    def test_extract_corrupted_file_raises_extraction_error(
        self, tmp_path: Path
    ) -> None:
        """破損したPDFファイルでExtractionErrorが発生する"""
        corrupted = tmp_path / "corrupted.pdf"
        corrupted.write_bytes(b"not a real pdf content")
        with pytest.raises(ExtractionError, match="読み取りに失敗しました"):
            self.extractor.extract(str(corrupted))


class TestPDFExtractorCalculateHash:
    """PDFExtractor.calculate_hash() のテスト"""

    def setup_method(self) -> None:
        self.extractor = PDFExtractor()

    def test_calculate_hash_returns_64_char_hex(self, sample_pdf_en: Path) -> None:
        """ハッシュが64文字の16進数文字列である"""
        result = self.extractor.calculate_hash(str(sample_pdf_en))

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_calculate_hash_is_deterministic(self, sample_pdf_en: Path) -> None:
        """同一ファイルに対して同じハッシュを返す"""
        hash1 = self.extractor.calculate_hash(str(sample_pdf_en))
        hash2 = self.extractor.calculate_hash(str(sample_pdf_en))

        assert hash1 == hash2

    def test_calculate_hash_differs_for_different_files(
        self, sample_pdf_en: Path, sample_pdf_ja: Path
    ) -> None:
        """異なるファイルに対して異なるハッシュを返す"""
        hash_en = self.extractor.calculate_hash(str(sample_pdf_en))
        hash_ja = self.extractor.calculate_hash(str(sample_pdf_ja))

        assert hash_en != hash_ja
