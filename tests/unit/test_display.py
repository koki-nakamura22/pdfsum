"""display.py のユニットテスト"""

from datetime import datetime

from pdfsum.cli.display import (
    print_error,
    print_progress,
    print_success,
    print_summary_detail,
    print_summary_list,
    print_summary_result,
)
from pdfsum.models.summary import Summary


def _make_summary(
    summary_id: str = "a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6",
) -> Summary:
    """テスト用Summaryオブジェクトを生成する"""
    return Summary(
        id=summary_id,
        pdf_path="/path/to/doc.pdf",
        pdf_hash="abc123hash",
        file_name="doc.pdf",
        page_count=42,
        summary_text="テスト要約テキスト",
        summary_length="standard",
        model_name="gemini-2.5-flash",
        created_at=datetime(2026, 2, 28, 10, 30, 0),
    )


class TestPrintSummaryResult:
    """print_summary_result のテスト"""

    def test_contains_file_name(self, capsys: object) -> None:
        """ファイル名が出力に含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_result(summary)
        captured = capsys.readouterr()
        assert "doc.pdf" in captured.out

    def test_contains_page_count(self, capsys: object) -> None:
        """ページ数が出力に含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_result(summary)
        captured = capsys.readouterr()
        assert "42ページ" in captured.out

    def test_contains_summary_text(self, capsys: object) -> None:
        """要約テキストが出力に含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_result(summary)
        captured = capsys.readouterr()
        assert "テスト要約テキスト" in captured.out

    def test_contains_model_name(self, capsys: object) -> None:
        """モデル名が出力に含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_result(summary)
        captured = capsys.readouterr()
        assert "gemini-2.5-flash" in captured.out

    def test_contains_summary_id(self, capsys: object) -> None:
        """要約IDが出力に含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_result(summary)
        captured = capsys.readouterr()
        assert "a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6" in captured.out


class TestPrintSummaryList:
    """print_summary_list のテスト"""

    def test_short_id_display(self, capsys: object) -> None:
        """短縮IDでテーブル表示する"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summaries = [_make_summary()]
        print_summary_list(summaries)
        captured = capsys.readouterr()
        assert "a1b2c3d4" in captured.out
        # 完全UUIDは含まれない
        assert "e5f6-4a8b" not in captured.out

    def test_full_id_display(self, capsys: object) -> None:
        """full_id=Trueで完全UUIDを表示する"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summaries = [_make_summary()]
        print_summary_list(summaries, full_id=True)
        captured = capsys.readouterr()
        assert "a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6" in captured.out

    def test_empty_list_message(self, capsys: object) -> None:
        """空リスト時にメッセージを表示する"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        print_summary_list([])
        captured = capsys.readouterr()
        assert "保存済みの要約はありません" in captured.out

    def test_contains_file_name_and_length(
        self, capsys: object
    ) -> None:
        """ファイル名と要約長が含まれる"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summaries = [_make_summary()]
        print_summary_list(summaries)
        captured = capsys.readouterr()
        assert "doc.pdf" in captured.out
        assert "standard" in captured.out

    def test_truncates_long_file_names(self, capsys: object) -> None:
        """24文字を超えるファイル名を切り詰める"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = Summary(
            id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6",
            pdf_path="/path/to/very_long_file_name_exceeds.pdf",
            pdf_hash="abc123hash",
            file_name="very_long_file_name_exceeds.pdf",
            page_count=42,
            summary_text="要約",
            summary_length="standard",
            model_name="gemini-2.5-flash",
            created_at=datetime(2026, 2, 28, 10, 30, 0),
        )
        print_summary_list([summary])
        captured = capsys.readouterr()
        assert "..." in captured.out


class TestPrintSummaryDetail:
    """print_summary_detail のテスト"""

    def test_contains_all_fields(self, capsys: object) -> None:
        """全フィールドが表示される"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        summary = _make_summary()
        print_summary_detail(summary)
        captured = capsys.readouterr()
        assert "a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6" in captured.out
        assert "doc.pdf" in captured.out
        assert "/path/to/doc.pdf" in captured.out
        assert "42" in captured.out
        assert "standard" in captured.out
        assert "gemini-2.5-flash" in captured.out
        assert "テスト要約テキスト" in captured.out
        assert "2026-02-28" in captured.out


class TestPrintProgress:
    """print_progress のテスト"""

    def test_displays_step_and_message(
        self, capsys: object
    ) -> None:
        """ステップ番号とメッセージが表示される"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        print_progress(1, 3, "テスト処理中...")
        captured = capsys.readouterr()
        assert "[1/3]" in captured.out
        assert "テスト処理中..." in captured.out


class TestPrintError:
    """print_error のテスト"""

    def test_displays_error_prefix(self, capsys: object) -> None:
        """エラープレフィックス付きで表示する"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        print_error("テストエラー")
        captured = capsys.readouterr()
        assert "エラー: テストエラー" in captured.err


class TestPrintSuccess:
    """print_success のテスト"""

    def test_displays_success_message(self, capsys: object) -> None:
        """成功メッセージを表示する"""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)
        print_success("テスト成功")
        captured = capsys.readouterr()
        assert "テスト成功" in captured.out
