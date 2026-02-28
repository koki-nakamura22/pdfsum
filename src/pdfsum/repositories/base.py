"""要約リポジトリの抽象基底クラス"""

from abc import ABC, abstractmethod

from pdfsum.models.summary import Summary


class SummaryRepository(ABC):
    """要約結果の永続化インターフェース"""

    @abstractmethod
    def save(self, summary: Summary) -> None:
        """要約を保存する。

        Args:
            summary: 保存する要約オブジェクト
        """
        ...

    @abstractmethod
    def find_by_id(self, summary_id: str) -> Summary | None:
        """完全なIDで要約を取得する。

        Args:
            summary_id: UUID v4形式の要約ID

        Returns:
            要約オブジェクト。見つからない場合はNone
        """
        ...

    @abstractmethod
    def find_by_id_prefix(self, id_prefix: str) -> list[Summary]:
        """IDの前方一致で要約を検索する（短縮ID解決用）。

        Args:
            id_prefix: IDの先頭部分（通常8文字）

        Returns:
            一致した要約のリスト
        """
        ...

    @abstractmethod
    def find_by_hash(self, pdf_hash: str, summary_length: str) -> Summary | None:
        """PDFハッシュと要約長で要約を検索する。

        Args:
            pdf_hash: PDFファイルのSHA-256ハッシュ
            summary_length: 要約の長さ ("short", "standard", "detailed")

        Returns:
            要約オブジェクト。見つからない場合はNone
        """
        ...

    @abstractmethod
    def find_all(self) -> list[Summary]:
        """全要約を取得する。作成日時の降順で返す。

        Returns:
            要約のリスト
        """
        ...

    @abstractmethod
    def delete(self, summary_id: str) -> bool:
        """要約を削除する。

        Args:
            summary_id: 削除する要約のID

        Returns:
            削除に成功した場合True、見つからない場合False
        """
        ...
