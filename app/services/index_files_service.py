from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.rag_file import RagFile
from models.rag_index import RagIndex
from models.rag_index_file import RagIndexFile
from services.providers_connections_service import ProvidersConnectionsService
from services.provider_file_uploads_service import ProviderFileUploadsService

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

        # Загружаем файл в провайдер если у индекса есть external_id
        external_id = None
        chunking_strategy = rag_file.chunking_strategy  # По умолчанию берем из файла
        
        if rag_index.external_id:
            try:
                provider_service = ProvidersConnectionsService(db=self._db)
                provider = provider_service.get_provider(rag_index.provider_type)
                
                # Загружаем файл в провайдер
                upload_service = ProviderFileUploadsService(db=self._db)
                upload = upload_service.get_or_sync(
                    provider_type=rag_index.provider_type,
                    local_file_id=file_id,
                    force=False,
                    meta={"chunking_strategy": chunking_strategy} if chunking_strategy else None
                )
                
                external_id = upload.external_file_id
                
                # Привязываем файл к vector store в провайдере
                provider.attach_file_to_vector_store(
                    vector_store_id=rag_index.external_id,
                    file_id=external_id
                )
                
            except Exception:
                # Если не удалось загрузить, все равно создаем связку но без external_id
                # Это позволит повторить попытку позже через синхронизацию
                pass

        link = RagIndexFile(
            index_id=index_id,
            file_id=file_id,
            include_order=next_order,
            external_id=external_id,
            chunking_strategy=chunking_strategy,
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
