"""SingleFileSource のユニットテスト"""

from pathlib import Path

from pdfsum.digest.source import SingleFileSource


class TestSingleFileSourceFetch:
    """SingleFileSource.fetch() のテスト"""

    def test_existing_file_yields_one_item(self, tmp_path: Path) -> None:
        """存在するファイルに対して1件の Item を yield する"""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"dummy")
        source = SingleFileSource(pdf)

        result = list(source.fetch())

        assert len(result) == 1

    def test_item_id_is_resolved_absolute_path(self, tmp_path: Path) -> None:
        """Item.id が resolve 済みの絶対パス文字列である"""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"dummy")
        source = SingleFileSource(pdf)

        item = list(source.fetch())[0]

        assert item.id == str(pdf.resolve())

    def test_item_payload_is_path_object(self, tmp_path: Path) -> None:
        """Item.payload が Path オブジェクトである"""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"dummy")
        source = SingleFileSource(pdf)

        item = list(source.fetch())[0]

        assert isinstance(item.payload, Path)

    def test_nonexistent_file_yields_nothing(self, tmp_path: Path) -> None:
        """存在しないファイルパスに対して空の iterable を返す"""
        source = SingleFileSource(tmp_path / "missing.pdf")

        result = list(source.fetch())

        assert result == []

    def test_directory_yields_nothing(self, tmp_path: Path) -> None:
        """ディレクトリパスに対して空の iterable を返す"""
        source = SingleFileSource(tmp_path)

        result = list(source.fetch())

        assert result == []

    def test_relative_path_is_resolved(self, tmp_path: Path, monkeypatch: object) -> None:
        """相対パス入力でも Item.id が絶対パス文字列になる"""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"dummy")
        # cwd を tmp_path に変更して相対パスを使えるようにする
        import os
        monkeypatch.chdir(tmp_path)
        source = SingleFileSource("doc.pdf")

        item = list(source.fetch())[0]

        assert Path(item.id).is_absolute()
        assert item.id == str(pdf.resolve())

    def test_str_path_is_accepted(self, tmp_path: Path) -> None:
        """文字列パスを受け付ける"""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"dummy")
        source = SingleFileSource(str(pdf))

        result = list(source.fetch())

        assert len(result) == 1
