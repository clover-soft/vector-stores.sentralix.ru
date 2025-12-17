from __future__ import annotations

from sqlalchemy.orm import Session

from models.rag_index import RagIndex
from services.providers_connections_service import ProvidersConnectionsService


class IndexSearchService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def search(
        self,
        *,
        index_id: str,
        query: str | list[str],
        filters: dict | None = None,
        max_num_results: int | None = None,
        ranking_options: dict | None = None,
        rewrite_query: bool | None = None,
    ) -> list[dict]:
        rag_index = (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .filter(RagIndex.id == index_id)
            .one_or_none()
        )
        if rag_index is None:
            raise ValueError("Индекс не найден")

        if not rag_index.external_id:
            raise ValueError("У индекса нет external_id")

        provider = ProvidersConnectionsService(db=self._db).get_provider(rag_index.provider_type)
        items = provider.search_vector_store(
            str(rag_index.external_id),
            query=query,
            filters=filters,
            max_num_results=max_num_results,
            ranking_options=ranking_options,
            rewrite_query=rewrite_query,
        )

        if not isinstance(items, list):
            return []

        out: list[dict] = []
        for item in items:
            if isinstance(item, dict):
                out.append(item)
        return out
