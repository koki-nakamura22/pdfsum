"""pytest フィクスチャ定義"""

from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def sample_pdf_en(tmp_path: Path) -> Path:
    """テスト用の英語PDFファイルを生成する"""
    pdf_path = tmp_path / "sample_en.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "This is a sample PDF document for testing.\n"
        "It contains English text across multiple lines.\n"
        "The purpose is to verify text extraction functionality.",
        fontsize=12,
    )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_pdf_ja(tmp_path: Path) -> Path:
    """テスト用の日本語PDFファイルを生成する。

    pymupdf.Story APIを使いHTML経由で日本語テキストを埋め込む。
    環境にCJKフォントがなくてもpymupdf組み込みフォントで生成できる。
    """
    pdf_path = tmp_path / "sample_ja.pdf"
    html = (
        '<p style="font-family: sans-serif;">'
        "これはテスト用のPDFドキュメントです。"
        "日本語テキストの抽出を検証します。"
        "</p>"
    )
    story = pymupdf.Story(html=html)
    writer = pymupdf.DocumentWriter(str(pdf_path))
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + pymupdf.Rect(72, 72, -72, -72)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return pdf_path


@pytest.fixture
def sample_pdf_multipage(tmp_path: Path) -> Path:
    """テスト用の複数ページPDFファイルを生成する"""
    pdf_path = tmp_path / "multipage.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {i + 1} content.\nThis is page number {i + 1}.",
            fontsize=12,
        )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """テスト用の空PDFファイルを生成する（テキストなし）"""
    pdf_path = tmp_path / "empty.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def non_pdf_file(tmp_path: Path) -> Path:
    """テスト用の非PDFファイルを生成する"""
    file_path = tmp_path / "not_a_pdf.txt"
    file_path.write_text("This is not a PDF file.")
    return file_path
