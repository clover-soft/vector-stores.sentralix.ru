from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.rag_file import RagFile
from models.rag_index import RagIndex
from models.rag_index_file import RagIndexFile

_INCLUDE_ORDER_START = 1


class IndexFilesService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def _get_index(self, index_id: str) -> RagIndex | None:
        return (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .filter(RagIndex.id == index_id)
            .one_or_none()
        )

    def _get_file(self, file_id: str) -> RagFile | None:
        return (
            self._db.query(RagFile)
            .filter(RagFile.domain_id == self._domain_id)
            .filter(RagFile.id == file_id)
            .one_or_none()
        )

    def attach_file(self, index_id: str, file_id: str) -> None:
        rag_index = self._get_index(index_id)
        if rag_index is None:
            raise ValueError("Индекс не найден")

        rag_file = self._get_file(file_id)
        if rag_file is None:
            raise ValueError("Файл не найден")

        exists = (
            self._db.query(RagIndexFile)
            .filter(RagIndexFile.index_id == index_id)
            .filter(RagIndexFile.file_id == file_id)
            .one_or_none()
        )
        if exists is not None:
            raise ValueError("Файл уже привязан к индексу")

        max_order = (
            self._db.query(func.max(RagIndexFile.include_order))
            .filter(RagIndexFile.index_id == index_id)
            .scalar()
        )
        next_order = (max_order or 0) + 1
        if next_order <= 0:
            next_order = _INCLUDE_ORDER_START

        link = RagIndexFile(
            index_id=index_id,
            file_id=file_id,
            include_order=next_order,
        )
        self._db.add(link)
        self._db.commit()

    def detach_file(self, index_id: str, file_id: str) -> bool:
        rag_index = self._get_index(index_id)
        if rag_index is None:
            return False

        link = (
            self._db.query(RagIndexFile)
            .filter(RagIndexFile.index_id == index_id)
            .filter(RagIndexFile.file_id == file_id)
            .one_or_none()
        )
        if link is None:
            return False

        self._db.delete(link)
        self._db.commit()
        return True

    def list_files(self, index_id: str) -> list[tuple[int, RagFile]] | None:
        rag_index = self._get_index(index_id)
        if rag_index is None:
            return None

        rows = (
            self._db.query(RagIndexFile.include_order, RagFile)
            .join(RagFile, RagFile.id == RagIndexFile.file_id)
            .filter(RagIndexFile.index_id == index_id)
            .filter(RagFile.domain_id == self._domain_id)
            .order_by(RagIndexFile.include_order.asc())
            .all()
        )
        return [(include_order, rag_file) for include_order, rag_file in rows]
