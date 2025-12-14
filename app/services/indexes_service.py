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
        name: str | None,
        description: str | None,
        chunking_strategy: dict | None,
        expires_after: dict | None,
        file_ids: list[str] | None,
        metadata: dict[str, str] | None,
    ) -> RagIndex:
        index_id = str(uuid4())

        rag_index = RagIndex(
            id=index_id,
            domain_id=self._domain_id,
            provider_type=provider_type,
            name=name,
            description=description,
            chunking_strategy=chunking_strategy,
            expires_after=expires_after,
            file_ids=file_ids,
            metadata_=metadata,
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
        name: str | None,
        description: str | None,
        chunking_strategy: dict | None,
        expires_after: dict | None,
        file_ids: list[str] | None,
        metadata: dict[str, str] | None,
    ) -> RagIndex | None:
        rag_index = self.get_index(index_id)
        if rag_index is None:
            return None

        if provider_type is not None:
            rag_index.provider_type = provider_type

        if name is not None:
            rag_index.name = name

        if description is not None:
            rag_index.description = description

        if chunking_strategy is not None:
            rag_index.chunking_strategy = chunking_strategy

        if expires_after is not None:
            rag_index.expires_after = expires_after

        if file_ids is not None:
            rag_index.file_ids = file_ids

        if metadata is not None:
            rag_index.metadata_ = metadata

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
