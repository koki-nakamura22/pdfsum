"""ChunkedSummarizer のユニットテスト"""

from unittest.mock import MagicMock

from pdfsum.engines.base import SummarizerEngine
from pdfsum.engines.chunked import ChunkedSummarizer
from pdfsum.models.summary import ExtractedPage


def _make_mock_engine(max_tokens: int = 1000) -> MagicMock:
    """モック要約エンジンを生成する"""
    engine = MagicMock(spec=SummarizerEngine)
    engine.get_max_input_tokens.return_value = max_tokens
    engine.summarize.return_value = "要約結果"
    engine.get_model_name.return_value = "test-model"
    return engine


class TestChunkedSummarizerEstimateTokens:
    """ChunkedSummarizer.estimate_tokens() のテスト"""

    def test_estimate_japanese_text(self) -> None:
        """日本語テキストのトークン数推定"""
        engine = _make_mock_engine()
        chunked = ChunkedSummarizer(engine)

        # 10文字の日本語 → 約15トークン
        result = chunked.estimate_tokens("あ" * 10)
        assert result == 15

    def test_estimate_english_text(self) -> None:
        """英語テキストのトークン数推定"""
        engine = _make_mock_engine()
        chunked = ChunkedSummarizer(engine)

        # 10単語の英語 → 約13トークン
        result = chunked.estimate_tokens("word " * 10)
        assert result == 13

    def test_estimate_mixed_text(self) -> None:
        """日英混合テキストのトークン数推定"""
        engine = _make_mock_engine()
        chunked = ChunkedSummarizer(engine)

        result = chunked.estimate_tokens("日本語text")
        assert result > 0


class TestChunkedSummarizerSummarize:
    """ChunkedSummarizer.summarize() のテスト"""

    def test_summarize_short_text_calls_engine_directly(self) -> None:
        """短いテキストはチャンク分割せずにエンジンを直接呼ぶ"""
        engine = _make_mock_engine(max_tokens=100_000)
        chunked = ChunkedSummarizer(engine)

        result = chunked.summarize("短いテキスト", "standard")

        assert result == "要約結果"
        engine.summarize.assert_called_once_with("短いテキスト", "standard")

    def test_summarize_long_text_splits_into_chunks(self) -> None:
        """長いテキストはチャンク分割してエンジンを複数回呼ぶ"""
        engine = _make_mock_engine(max_tokens=100)
        engine.summarize.return_value = "チャンク要約"
        chunked = ChunkedSummarizer(engine)

        # max_tokens=100の80%=80トークン超のテキスト
        long_text = "あ" * 200
        chunked.summarize(long_text, "standard")

        # エンジンが複数回呼ばれることを確認
        assert engine.summarize.call_count > 1

    def test_summarize_with_pages_splits_by_page_boundary(self) -> None:
        """ページ情報がある場合はページ境界で分割する"""
        engine = _make_mock_engine(max_tokens=100)
        engine.summarize.return_value = "ページ要約"
        chunked = ChunkedSummarizer(engine)

        pages = [
            ExtractedPage(page_number=1, text="あ" * 100),
            ExtractedPage(page_number=2, text="い" * 100),
            ExtractedPage(page_number=3, text="う" * 100),
        ]
        total_text = "\n".join(p.text for p in pages)

        chunked.summarize(total_text, "standard", pages=pages)

        assert engine.summarize.call_count > 1

    def test_summarize_respects_max_recursion_depth(self) -> None:
        """再帰上限に達した場合にテキストを切り詰めて要約する"""
        engine = _make_mock_engine(max_tokens=10)
        # 常に長い結果を返し再帰を促す
        call_count = 0

        def side_effect(text: str, length: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count > 20:
                return "最終要約"
            return "あ" * 200

        engine.summarize.side_effect = side_effect
        chunked = ChunkedSummarizer(engine)

        result = chunked.summarize("あ" * 200, "standard")

        # 再帰上限(5回)以内で完了すること
        assert result is not None

    def test_split_by_size_truncates_oversized_paragraph(self) -> None:
        """単一段落がmax_tokensを超える場合に切り詰める"""
        engine = _make_mock_engine(max_tokens=50)
        engine.summarize.return_value = "切り詰め要約"
        chunked = ChunkedSummarizer(engine)

        # 1つの段落がmax_tokensを大幅に超えるテキスト（段落区切りなし）
        oversized_text = "あ" * 500
        chunked.summarize(oversized_text, "standard")

        # エンジンが呼ばれ、テキストが切り詰められていることを確認
        first_call_text = engine.summarize.call_args_list[0][0][0]
        assert len(first_call_text) < len(oversized_text)

    def test_split_by_pages_truncates_oversized_page(self) -> None:
        """単一ページがmax_tokensを超える場合に切り詰める"""
        engine = _make_mock_engine(max_tokens=50)
        engine.summarize.return_value = "切り詰め要約"
        chunked = ChunkedSummarizer(engine)

        pages = [
            ExtractedPage(page_number=1, text="あ" * 500),
        ]
        total_text = pages[0].text

        chunked.summarize(total_text, "standard", pages=pages)

        # エンジンが呼ばれ、テキストが切り詰められていることを確認
        first_call_text = engine.summarize.call_args_list[0][0][0]
        assert len(first_call_text) < len(total_text)

    def test_split_by_pages_flushes_current_chunk_before_oversized_page(
        self,
    ) -> None:
        """通常ページ蓄積後に巨大ページが来た場合、蓄積分をflushしてから切り詰める"""
        engine = _make_mock_engine(max_tokens=100)
        engine.summarize.return_value = "要約"
        chunked = ChunkedSummarizer(engine)

        pages = [
            ExtractedPage(page_number=1, text="あ" * 30),  # 通常サイズ
            ExtractedPage(page_number=2, text="い" * 30),  # 通常サイズ
            ExtractedPage(page_number=3, text="う" * 500),  # 巨大ページ
        ]
        total_text = "\n".join(p.text for p in pages)

        chunked.summarize(total_text, "standard", pages=pages)

        # 3チャンク以上: 蓄積分 + 巨大ページ(truncated) + 最終要約
        assert engine.summarize.call_count >= 3

    def test_split_by_pages_accumulates_normal_pages(self) -> None:
        """通常サイズのページが蓄積され最後にflushされる"""
        engine = _make_mock_engine(max_tokens=500)
        engine.summarize.return_value = "要約"
        chunked = ChunkedSummarizer(engine)

        pages = [
            ExtractedPage(page_number=1, text="あ" * 10),
            ExtractedPage(page_number=2, text="い" * 10),
            ExtractedPage(page_number=3, text="う" * 10),
        ]
        total_text = "\n".join(p.text for p in pages)

        result = chunked.summarize(total_text, "standard", pages=pages)

        # max_tokens内に収まるので直接要約される
        assert result == "要約"
        engine.summarize.assert_called_once()

    def test_split_by_size_flushes_current_chunk_before_oversized_paragraph(
        self,
    ) -> None:
        """通常段落蓄積後に巨大段落が来た場合、蓄積分をflushしてから切り詰める"""
        engine = _make_mock_engine(max_tokens=100)
        engine.summarize.return_value = "要約"
        chunked = ChunkedSummarizer(engine)

        # 通常段落 + 巨大段落を段落区切りで結合
        text = "あ" * 30 + "\n\n" + "い" * 30 + "\n\n" + "う" * 500

        chunked.summarize(text, "standard")

        # 3チャンク以上: 蓄積分 + 巨大段落(truncated) + 最終要約
        assert engine.summarize.call_count >= 3

    def test_split_by_size_accumulates_normal_paragraphs(self) -> None:
        """通常サイズの段落が蓄積され最後にflushされる"""
        engine = _make_mock_engine(max_tokens=500)
        engine.summarize.return_value = "要約"
        chunked = ChunkedSummarizer(engine)

        text = "あ" * 10 + "\n\n" + "い" * 10 + "\n\n" + "う" * 10

        result = chunked.summarize(text, "standard")

        # max_tokens内に収まるので直接要約される
        assert result == "要約"
        engine.summarize.assert_called_once()

    def test_truncate_to_tokens_returns_text_within_limit(self) -> None:
        """トークン上限内のテキストはそのまま返す"""
        engine = _make_mock_engine(max_tokens=1000)
        chunked = ChunkedSummarizer(engine)

        short_text = "あ" * 10  # 15トークン程度
        result = chunked._truncate_to_tokens(short_text, 1000)
        assert result == short_text
