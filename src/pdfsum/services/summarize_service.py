"""要約サービス"""

import uuid
from datetime import datetime

from pdfsum.engines.base import SummarizerEngine
from pdfsum.engines.chunked import ChunkedSummarizer
from pdfsum.extractors.pdf_extractor import PDFExtractor
from pdfsum.models.summary import PdfsumError, Summary
from pdfsum.repositories.base import SummaryRepository


class SummarizeService:
    """PDF要約のユースケースを統合するサービス"""

    def __init__(
        self,
        extractor: PDFExtractor,
        engine: SummarizerEngine,
        repository: SummaryRepository,
    ) -> None:
        self._extractor = extractor
        self._engine = engine
        self._repository = repository
        self._chunked = ChunkedSummarizer(engine)

    def summarize(self, pdf_path: str, length: str) -> Summary:
        """PDFを要約する。キャッシュがあればそれを返す。

        Args:
            pdf_path: PDFファイルのパス
            length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約結果のSummaryオブジェクト

        Raises:
            FileNotFoundError: PDFファイルが存在しない場合
            ExtractionError: テキスト抽出に失敗した場合
            SummarizationError: 要約生成に失敗した場合
        """
        document = self._extractor.extract(pdf_path)

        cached = self._repository.find_by_hash(document.pdf_hash, length)
        if cached is not None:
            return cached

        summary_text = self._chunked.summarize(
            document.total_text, length, pages=document.pages
        )

        summary = Summary(
            id=str(uuid.uuid4()),
            pdf_path=document.pdf_path,
            pdf_hash=document.pdf_hash,
            file_name=document.file_name,
            page_count=document.page_count,
            summary_text=summary_text,
            summary_length=length,
            model_name=self._engine.get_model_name(),
            created_at=datetime.now(),
        )

        self._repository.save(summary)
        return summary

    def list_summaries(self) -> list[Summary]:
        """保存済み要約の一覧を返す。

        Returns:
            要約のリスト（作成日時の降順）
        """
        return self._repository.find_all()

    def get_summary(self, summary_id: str) -> Summary | None:
        """完全なIDで要約を取得する。

        Args:
            summary_id: UUID v4形式の要約ID

        Returns:
            要約オブジェクト。見つからない場合はNone
        """
        return self._repository.find_by_id(summary_id)

    def get_summary_by_prefix(self, id_prefix: str) -> Summary:
        """短縮IDから要約を取得する。

        Args:
            id_prefix: IDの先頭部分

        Returns:
            一意に特定された要約オブジェクト

        Raises:
            PdfsumError: 0件または複数一致の場合
        """
        matches = self._repository.find_by_id_prefix(id_prefix)

        if len(matches) == 0:
            raise PdfsumError(
                f"要約が見つかりません (ID: {id_prefix})"
            )
        if len(matches) > 1:
            raise PdfsumError(
                f"ID '{id_prefix}' に複数の要約が一致しました。"
                f"完全なIDを指定してください"
            )

        return matches[0]

    def delete_summary(self, summary_id: str) -> bool:
        """完全なIDで要約を削除する。

        Args:
            summary_id: 削除する要約のID

        Returns:
            削除に成功した場合True、見つからない場合False
        """
        return self._repository.delete(summary_id)

    def resolve_and_delete(self, id_prefix: str) -> bool:
        """短縮IDから要約を解決して削除する。

        Args:
            id_prefix: IDの先頭部分

        Returns:
            削除に成功した場合True

        Raises:
            PdfsumError: 0件または複数一致の場合
        """
        summary = self.get_summary_by_prefix(id_prefix)
        return self._repository.delete(summary.id)
