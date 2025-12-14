from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from models.rag_index import RagIndex


class IndexesService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def create_index(
        self,
        provider_type: str,
        index_type: str,
        max_chunk_size: int | None,
        chunk_overlap: int | None,
        provider_ttl_days: int | None,
        description: str | None,
    ) -> RagIndex:
        index_id = str(uuid4())

        rag_index = RagIndex(
            id=index_id,
            domain_id=self._domain_id,
            provider_type=provider_type,
            index_type=index_type,
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            provider_ttl_days=provider_ttl_days,
            description=description,
            indexing_status="not_indexed",
        )

        self._db.add(rag_index)
        self._db.commit()
        self._db.refresh(rag_index)
        return rag_index

    def list_indexes(self, skip: int = 0, limit: int = 100) -> list[RagIndex]:
        return (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .order_by(RagIndex.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_index(self, index_id: str) -> RagIndex | None:
        return (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .filter(RagIndex.id == index_id)
            .one_or_none()
        )

    def update_index(
        self,
        index_id: str,
        provider_type: str | None,
        index_type: str | None,
        max_chunk_size: int | None,
        chunk_overlap: int | None,
        provider_ttl_days: int | None,
        description: str | None,
    ) -> RagIndex | None:
        rag_index = self.get_index(index_id)
        if rag_index is None:
            return None

        if provider_type is not None:
            rag_index.provider_type = provider_type

        if index_type is not None:
            rag_index.index_type = index_type

        if max_chunk_size is not None:
            rag_index.max_chunk_size = max_chunk_size

        if chunk_overlap is not None:
            rag_index.chunk_overlap = chunk_overlap

        if provider_ttl_days is not None:
            rag_index.provider_ttl_days = provider_ttl_days

        if description is not None:
            rag_index.description = description

        self._db.commit()
        self._db.refresh(rag_index)
        return rag_index

    def delete_index(self, index_id: str) -> bool:
        rag_index = self.get_index(index_id)
        if rag_index is None:
            return False

        self._db.delete(rag_index)
        self._db.commit()
        return True
