"""app.py のユニットテスト"""

from argparse import Namespace
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from pdfsum.cli.app import (
    _is_full_uuid,
    _is_short_id,
    _validate_id,
    cmd_delete,
    cmd_list,
    cmd_show,
    cmd_summarize,
    main,
)
from pdfsum.models.summary import PdfsumError, Summary


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


class TestIsFullUUID:
    """_is_full_uuid のテスト"""

    def test_valid_uuid_returns_true(self) -> None:
        """完全なUUID v4で True を返す"""
        assert _is_full_uuid("a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6")

    def test_short_id_returns_false(self) -> None:
        """短縮IDで False を返す"""
        assert not _is_full_uuid("a1b2c3d4")

    def test_invalid_format_returns_false(self) -> None:
        """無効な形式で False を返す"""
        assert not _is_full_uuid("not-a-uuid")

    def test_uppercase_returns_false(self) -> None:
        """大文字を含むUUIDで False を返す"""
        assert not _is_full_uuid("A1B2C3D4-E5F6-4A8B-9C0D-E1F2A3B4C5D6")


class TestIsShortId:
    """_is_short_id のテスト"""

    def test_valid_short_id_returns_true(self) -> None:
        """8文字16進数で True を返す"""
        assert _is_short_id("a1b2c3d4")

    def test_full_uuid_returns_false(self) -> None:
        """完全UUIDで False を返す"""
        assert not _is_short_id("a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6")

    def test_too_short_returns_false(self) -> None:
        """7文字で False を返す"""
        assert not _is_short_id("a1b2c3d")

    def test_non_hex_returns_false(self) -> None:
        """非16進数文字を含む場合 False を返す"""
        assert not _is_short_id("a1b2g3d4")


class TestValidateId:
    """_validate_id のテスト"""

    def test_valid_uuid_does_not_raise(self) -> None:
        """完全UUIDで例外を投げない"""
        _validate_id("a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6")

    def test_valid_short_id_does_not_raise(self) -> None:
        """短縮IDで例外を投げない"""
        _validate_id("a1b2c3d4")

    def test_invalid_format_raises_pdfsum_error(self) -> None:
        """無効な形式で PdfsumError を投げる"""
        with pytest.raises(PdfsumError, match="無効なID形式です"):
            _validate_id("invalid-id")


class TestCmdSummarize:
    """cmd_summarize のテスト"""

    @patch("pdfsum.cli.app._build_service_for_summarize")
    def test_returns_zero_on_success(self, mock_build: Mock) -> None:
        """要約成功時に終了コード0を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.summarize.return_value = _make_summary()

        args = Namespace(pdf_path="/test.pdf", length="standard")
        assert cmd_summarize(args) == 0

    @patch("pdfsum.cli.app._build_service_for_summarize")
    def test_calls_service_with_correct_args(
        self, mock_build: Mock
    ) -> None:
        """サービスに正しい引数を渡す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.summarize.return_value = _make_summary()

        args = Namespace(pdf_path="/test.pdf", length="short")
        cmd_summarize(args)
        mock_service.summarize.assert_called_once_with("/test.pdf", "short")


class TestCmdList:
    """cmd_list のテスト"""

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_returns_zero(self, mock_build: Mock) -> None:
        """一覧表示で終了コード0を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.list_summaries.return_value = []

        args = Namespace(full_id=False)
        assert cmd_list(args) == 0


class TestCmdShow:
    """cmd_show のテスト"""

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_full_uuid_found_returns_zero(self, mock_build: Mock) -> None:
        """完全UUID指定で見つかった場合に終了コード0を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.get_summary.return_value = _make_summary()

        args = Namespace(
            summary_id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6"
        )
        assert cmd_show(args) == 0

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_full_uuid_not_found_raises_error(
        self, mock_build: Mock
    ) -> None:
        """完全UUID指定で見つからない場合に PdfsumError を投げる"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.get_summary.return_value = None

        args = Namespace(
            summary_id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6"
        )
        with pytest.raises(PdfsumError, match="要約が見つかりません"):
            cmd_show(args)

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_short_id_calls_get_by_prefix(
        self, mock_build: Mock
    ) -> None:
        """短縮ID指定でget_summary_by_prefixを呼ぶ"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.get_summary_by_prefix.return_value = _make_summary()

        args = Namespace(summary_id="a1b2c3d4")
        assert cmd_show(args) == 0
        mock_service.get_summary_by_prefix.assert_called_once_with(
            "a1b2c3d4"
        )

    def test_invalid_id_raises_error(self) -> None:
        """無効なID形式で PdfsumError を投げる"""
        args = Namespace(summary_id="invalid")
        with pytest.raises(PdfsumError, match="無効なID形式です"):
            cmd_show(args)


class TestCmdDelete:
    """cmd_delete のテスト"""

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_full_uuid_found_returns_zero(self, mock_build: Mock) -> None:
        """完全UUID指定で削除成功時に終了コード0を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.delete_summary.return_value = True

        args = Namespace(
            summary_id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6"
        )
        assert cmd_delete(args) == 0

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_full_uuid_not_found_raises_error(
        self, mock_build: Mock
    ) -> None:
        """完全UUID指定で見つからない場合に PdfsumError を投げる"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.delete_summary.return_value = False

        args = Namespace(
            summary_id="a1b2c3d4-e5f6-4a8b-9c0d-e1f2a3b4c5d6"
        )
        with pytest.raises(PdfsumError, match="要約が見つかりません"):
            cmd_delete(args)

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_short_id_calls_resolve_and_delete(
        self, mock_build: Mock
    ) -> None:
        """短縮ID指定でresolve_and_deleteを呼ぶ"""
        mock_service = Mock()
        mock_build.return_value = mock_service

        args = Namespace(summary_id="a1b2c3d4")
        assert cmd_delete(args) == 0
        mock_service.resolve_and_delete.assert_called_once_with("a1b2c3d4")

    def test_invalid_id_raises_error(self) -> None:
        """無効なID形式で PdfsumError を投げる"""
        args = Namespace(summary_id="invalid")
        with pytest.raises(PdfsumError, match="無効なID形式です"):
            cmd_delete(args)


class TestMainFunction:
    """main関数のテスト"""

    def test_no_command_returns_exit_code_2(self) -> None:
        """コマンド未指定で終了コード2を返す"""
        assert main([]) == 2

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_list_command_returns_zero(self, mock_build: Mock) -> None:
        """list コマンドで終了コード0を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.list_summaries.return_value = []

        assert main(["list"]) == 0

    @patch("pdfsum.cli.app._build_service_for_readonly")
    def test_catches_pdfsum_error_returns_exit_code_1(
        self, mock_build: Mock
    ) -> None:
        """PdfsumError をキャッチして終了コード1を返す"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.list_summaries.side_effect = PdfsumError("テストエラー")

        assert main(["list"]) == 1

    def test_show_with_invalid_id_returns_exit_code_1(self) -> None:
        """show で無効なID指定時に終了コード1を返す"""
        assert main(["show", "invalid"]) == 1

    def test_version_flag_exits_zero(self) -> None:
        """--version で終了コード0を返す"""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
