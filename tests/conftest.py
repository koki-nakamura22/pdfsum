"""pytest フィクスチャ定義"""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


@pytest.fixture
def sample_pdf_en(tmp_path: Path) -> Path:
    """テスト用の英語PDFファイルを生成する"""
    pdf_path = tmp_path / "sample_en.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.drawString(72, 700, "This is a sample PDF document for testing.")
    c.drawString(72, 680, "It contains English text across multiple lines.")
    c.drawString(72, 660, "The purpose is to verify text extraction functionality.")
    c.save()
    return pdf_path


@pytest.fixture
def sample_pdf_ja(tmp_path: Path) -> Path:
    """テスト用の日本語PDFファイルを生成する。

    reportlab の CID フォント (HeiseiMin-W3) を使い日本語テキストを埋め込む。
    """
    pdf_path = tmp_path / "sample_ja.pdf"
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setFont("HeiseiMin-W3", 12)
    c.drawString(72, 700, "これはテスト用のPDFドキュメントです。")
    c.drawString(72, 680, "日本語テキストの抽出を検証します。")
    c.save()
    return pdf_path


@pytest.fixture
def sample_pdf_multipage(tmp_path: Path) -> Path:
    """テスト用の複数ページPDFファイルを生成する"""
    pdf_path = tmp_path / "multipage.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    for i in range(3):
        c.drawString(72, 700, f"Page {i + 1} content.")
        c.drawString(72, 680, f"This is page number {i + 1}.")
        c.showPage()
    c.save()
    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """テスト用の空PDFファイルを生成する（テキストなし）"""
    pdf_path = tmp_path / "empty.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.showPage()
    c.save()
    return pdf_path


@pytest.fixture
def non_pdf_file(tmp_path: Path) -> Path:
    """テスト用の非PDFファイルを生成する"""
    file_path = tmp_path / "not_a_pdf.txt"
    file_path.write_text("This is not a PDF file.")
    return file_path
