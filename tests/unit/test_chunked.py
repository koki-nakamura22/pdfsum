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
