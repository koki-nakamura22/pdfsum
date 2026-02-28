"""チャンク分割要約"""

import re

from pdfsum.engines.base import SummarizerEngine
from pdfsum.models.summary import ExtractedPage

TOKEN_SAFETY_MARGIN = 0.8
JAPANESE_TOKEN_RATIO = 1.5
ENGLISH_TOKEN_RATIO = 1.3
MAX_RECURSION_DEPTH = 5


class ChunkedSummarizer:
    """コンテキストウィンドウを超えるテキストをチャンク分割して段階的に要約する"""

    def __init__(self, engine: SummarizerEngine) -> None:
        self._engine = engine

    def summarize(
        self,
        text: str,
        length: str,
        pages: list[ExtractedPage] | None = None,
    ) -> str:
        """テキストを要約する。必要に応じてチャンク分割する。

        Args:
            text: 要約対象のテキスト
            length: 要約の長さ ("short", "standard", "detailed")
            pages: ページ単位のテキスト（チャンク分割時にページ境界で分割するため）

        Returns:
            要約テキスト
        """
        return self._summarize_recursive(text, length, pages, depth=0)

    def _summarize_recursive(
        self,
        text: str,
        length: str,
        pages: list[ExtractedPage] | None,
        depth: int,
    ) -> str:
        """再帰的にチャンク分割・要約を行う"""
        max_tokens = int(self._engine.get_max_input_tokens() * TOKEN_SAFETY_MARGIN)
        estimated_tokens = self.estimate_tokens(text)

        if estimated_tokens <= max_tokens:
            return self._engine.summarize(text, length)

        if depth >= MAX_RECURSION_DEPTH:
            # 再帰上限に達した場合はテキストを切り詰めて要約
            truncated = self._truncate_to_tokens(text, max_tokens)
            return self._engine.summarize(truncated, length)

        if pages and len(pages) > 1:
            chunks = self._split_by_pages(pages, max_tokens)
        else:
            chunks = self._split_by_size(text, max_tokens)

        chunk_summaries = [
            self._engine.summarize(chunk, "standard") for chunk in chunks
        ]
        combined = "\n\n".join(chunk_summaries)

        return self._summarize_recursive(combined, length, None, depth + 1)

    def estimate_tokens(self, text: str) -> int:
        """テキストのトークン数を推定する。

        日本語文字は1.5倍、英語単語は1.3倍で概算する。

        Args:
            text: 推定対象のテキスト

        Returns:
            推定トークン数
        """
        japanese_chars = len(re.findall(r"[\u3000-\u9fff\uf900-\ufaff]", text))
        ascii_text = re.sub(r"[\u3000-\u9fff\uf900-\ufaff]", "", text)
        english_words = len(ascii_text.split())

        return int(
            japanese_chars * JAPANESE_TOKEN_RATIO
            + english_words * ENGLISH_TOKEN_RATIO
        )

    def _split_by_pages(
        self, pages: list[ExtractedPage], max_tokens: int
    ) -> list[str]:
        """ページ境界でテキストをチャンクに分割する"""
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for page in pages:
            page_tokens = self.estimate_tokens(page.text)

            if current_tokens + page_tokens > max_tokens and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # 単一ページがmax_tokensを超える場合は切り詰め
            if page_tokens > max_tokens:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.append(self._truncate_to_tokens(page.text, max_tokens))
                continue

            current_chunk.append(page.text)
            current_tokens += page_tokens

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _split_by_size(self, text: str, max_tokens: int) -> list[str]:
        """トークン数ベースでテキストをチャンクに分割する"""
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)

            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # 単一段落がmax_tokensを超える場合は切り詰め
            if para_tokens > max_tokens:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.append(self._truncate_to_tokens(para, max_tokens))
                continue

            current_chunk.append(para)
            current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # 空チャンクが出来た場合の保護
        return [c for c in chunks if c.strip()]

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """テキストを指定トークン数に切り詰める"""
        estimated = self.estimate_tokens(text)
        if estimated <= max_tokens:
            return text
        ratio = max_tokens / estimated
        cut_length = int(len(text) * ratio)
        return text[:cut_length]
