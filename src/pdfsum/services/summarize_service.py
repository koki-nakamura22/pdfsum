"""SummarizeService: pdfsum の公開 API.

内部は digestkit パイプラインを組み立てて実行する薄い facade.
"""
from __future__ import annotations

from pathlib import Path

import digestkit
from digestkit.extractors import ExtractionError as DigestkitExtractionError
from digestkit.extractors import PDFExtractor
from digestkit.summarizers import ChunkedLLMSummarizer, LLMSummarizer
from digestkit.summarizers import SummarizationError as DigestkitSummarizationError

from pdfsum.config.manager import Config
from pdfsum.digest.sink import PdfsumSink
from pdfsum.digest.source import SingleFileSource
from pdfsum.errors import ExtractionError, SummarizationError
from pdfsum.models.summary import Summary
from pdfsum.repositories.sqlite import SummaryReader

# pdfsum 旧版 DEFAULT_PROMPTS (digestkit 全面置換前の挙動を維持するため、
# digestkit の DEFAULT_PROMPTS は使わず pdfsum 独自テンプレートを保持する).
# `{text}` は digestkit の prompts mapping が要求する placeholder。
_PDFSUM_DEFAULT_PROMPTS: dict[str, str] = {
    "short": (
        "以下のテキストの要点のみを箇条書きで簡潔に要約してください。"
        "300〜500文字程度で、最も重要なポイントだけを抽出してください。"
        "日本語で出力してください。\n\n{text}"
    ),
    "standard": (
        "以下のテキストの要点と重要な詳細を含めて要約してください。"
        "1000〜2000文字程度で、主要な論点と補足情報を整理してください。"
        "日本語で出力してください。\n\n{text}"
    ),
    "detailed": (
        "以下のテキストを章・セクションごとに概要と要点を含めて詳細に要約してください。"
        "3000〜5000文字程度で、構造を保ちながら網羅的に要約してください。"
        "日本語で出力してください。\n\n{text}"
    ),
}


class SummarizeService:
    """pdfsum 公開 API.

    通常は :func:`pdfsum.create_service` 経由で取得する。
    内部実装は digestkit パイプラインを組み立てて呼ぶ薄い facade。
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._reader = SummaryReader(config.database.path)

    def summarize(self, pdf_path: str | Path, length: str) -> Summary:
        return run_summarize(self._config, Path(pdf_path), length)

    def list_summaries(self) -> list[Summary]:
        return self._reader.list_all()

    def get_summary(self, summary_id: str) -> Summary | None:
        return self._reader.get(summary_id)

    def get_summary_by_prefix(self, id_prefix: str) -> Summary:
        return self._reader.get_by_prefix(id_prefix)

    def delete_summary(self, summary_id: str) -> bool:
        return self._reader.delete(summary_id)

    def resolve_and_delete(self, id_prefix: str) -> bool:
        target = self._reader.get_by_prefix(id_prefix)
        return self._reader.delete(target.id)


# ---------- 内部関数 (公開しない) ----------

def build_digester(
    config: Config,
    pdf_path: Path,
    length: str,
) -> digestkit.Digester:
    base_prompts = _resolve_prompts(config)
    prompts = _build_prompts(base_prompts, config.summary.extra_instructions)
    summarizer: LLMSummarizer | ChunkedLLMSummarizer
    if config.summary.chunked:
        # digestkit 0.1.0 のバグ回避: ChunkedLLMSummarizer はモデルの
        # context window 算出に litellm の `max_tokens` (= 出力上限) を
        # 使ってしまっており、例えば gemini-2.5-flash では 65,535 となり
        # 閾値が ~57k tokens に狭まる. 実際の入力 context window
        # (`max_input_tokens`) は 1,048,576 で旧 pdfsum も
        # `max_input_tokens * 0.8 ≒ 839k` を閾値にしていた. 同等の挙動を
        # 再現するため `chunk_size` を明示指定して digestkit 内部の
        # 自動算出を上書きする.
        summarizer = ChunkedLLMSummarizer(
            provider=config.llm.provider,
            model=config.llm.model,
            prompts=prompts,
            default_length=length,
            chunk_size=_resolve_chunk_size(config.llm.provider, config.llm.model),
        )
    else:
        summarizer = LLMSummarizer(
            provider=config.llm.provider,
            model=config.llm.model,
            prompts=prompts,
            default_length=length,
        )
    return digestkit.Digester(
        source=SingleFileSource(pdf_path),
        extractor=PDFExtractor(),
        summarizer=summarizer,
        sink=PdfsumSink(config.database.path, length=length),
        # OQ-02 (改訂): digestkit SeenStore を無効化する.
        # 旧 pdfsum では「summarize は毎回 summaries テーブルに新行を書く」挙動
        # だったため、SeenStore による「同一内容なら skip」は外部挙動を変えてしまう.
        # 例えば「summarize → delete → 同じ PDF を再 summarize」したとき、
        # SeenStore は記録が残っているため write をスキップし、その結果
        # latest_for_path が空になって PdfsumError になる回帰が発生する.
        seen_store=None,
        dedup_key=digestkit.content_sha256_key,
    )


def run_summarize(
    config: Config,
    pdf_path: Path,
    length: str,
) -> Summary:
    digester = build_digester(config, pdf_path, length)
    try:
        result = digester.run(limit=1, length=length)
    except DigestkitSummarizationError as e:
        raise SummarizationError(str(e)) from e
    except DigestkitExtractionError as e:
        raise ExtractionError(str(e)) from e
    if result.failures:
        f = result.failures[0]
        stage = str(getattr(f, "stage", ""))
        cause: BaseException = getattr(f, "error", Exception(str(f)))
        if stage == "extract":
            raise ExtractionError(str(cause)) from cause
        raise SummarizationError(str(cause)) from cause
    return SummaryReader(config.database.path).latest_for_path(pdf_path)


def _resolve_chunk_size(provider: str, model: str) -> int:
    """ChunkedLLMSummarizer に渡す chunk_size を litellm から取得.

    digestkit 0.1.0 が `max_tokens` (出力上限) を取り違えている問題を回避するため、
    litellm `get_model_info` から `max_input_tokens` を直接取得し、
    旧 pdfsum と同じ `max_input_tokens * 0.8` を閾値とする (旧 ChunkedSummarizer の
    TOKEN_SAFETY_MARGIN を踏襲).

    取得失敗時は安全側に倒して 32k tokens (典型的な小型モデル相当) を返す.
    """
    try:
        import litellm

        info = litellm.get_model_info(f"{provider}/{model}")
        max_input = int(info.get("max_input_tokens") or 0)
        if max_input > 0:
            return int(max_input * 0.8)
    except Exception:
        pass
    return 32_000


def _resolve_prompts(config: Config) -> dict[str, str]:
    """config.toml の prompt_short / prompt_standard / prompt_detailed を反映.

    各キーが空文字なら pdfsum 旧版 DEFAULT_PROMPTS を使う (旧挙動と一致).
    digestkit の DEFAULT_PROMPTS は使わない (旧 pdfsum とプロンプト文言が異なり、
    要約結果の傾向が変わってしまうため).
    """
    return {
        "short": config.summary.prompt_short or _PDFSUM_DEFAULT_PROMPTS["short"],
        "standard": config.summary.prompt_standard or _PDFSUM_DEFAULT_PROMPTS["standard"],
        "detailed": config.summary.prompt_detailed or _PDFSUM_DEFAULT_PROMPTS["detailed"],
    }


def _build_prompts(default: dict[str, str], extra: str) -> dict[str, str]:
    """extra_instructions が non-empty なら各テンプレ末尾に追記."""
    if not extra:
        return default
    return {k: f"{v}\n\n追加指示: {extra}" for k, v in default.items()}
