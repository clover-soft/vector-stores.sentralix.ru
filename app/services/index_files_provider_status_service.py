from __future__ import annotations

from sqlalchemy.orm import Session

from models.rag_file import RagFile
from models.rag_index import RagIndex
from models.rag_index_file import RagIndexFile
from models.rag_provider_file_upload import RagProviderFileUpload
from services.providers_connections_service import ProvidersConnectionsService

_DEFAULT_LIST_LIMIT = 1000


class IndexFilesProviderStatusService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def list_provider_files(self, *, index_id: str) -> dict:
        rag_index = (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .filter(RagIndex.id == index_id)
            .one_or_none()
        )
        if rag_index is None:
            raise ValueError("Индекс не найден")

        rows = (
            self._db.query(RagIndexFile.include_order, RagFile)
            .join(RagFile, RagFile.id == RagIndexFile.file_id)
            .filter(RagIndexFile.index_id == index_id)
            .filter(RagFile.domain_id == self._domain_id)
            .order_by(RagIndexFile.include_order.asc())
            .all()
        )

        local_files = [rag_file for _, rag_file in rows]
        local_file_ids = [f.id for f in local_files]

        uploads: list[RagProviderFileUpload] = []
        if local_file_ids:
            uploads = (
                self._db.query(RagProviderFileUpload)
                .filter(RagProviderFileUpload.provider_id == rag_index.provider_type)
                .filter(RagProviderFileUpload.local_file_id.in_(local_file_ids))
                .all()
            )

        upload_by_local_file_id: dict[str, RagProviderFileUpload] = {u.local_file_id: u for u in uploads}

        provider_vector_store_files_by_external_file_id: dict[str, dict] = {}
        errors: list[str] = []

        vector_store_id = str(rag_index.external_id) if rag_index.external_id else None
        if not vector_store_id:
            errors.append("У индекса нет external_id")
        else:
            try:
                provider = ProvidersConnectionsService(db=self._db).get_provider(rag_index.provider_type)
                items = provider.list_vector_store_files(vector_store_id, limit=_DEFAULT_LIST_LIMIT)
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        provider_file_id = self._extract_provider_file_id(item)
                        if provider_file_id:
                            provider_vector_store_files_by_external_file_id[provider_file_id] = item
            except Exception as e:
                errors.append(f"Ошибка получения списка файлов у провайдера: {e}")

        result_items: list[dict] = []
        for include_order, rag_file in rows:
            upload = upload_by_local_file_id.get(rag_file.id)
            provider_upload = None
            provider_vector_store_file = None

            if upload is not None:
                provider_upload = {
                    "status": upload.status,
                    "last_error": upload.last_error,
                    "external_file_id": upload.external_file_id,
                }

                if upload.external_file_id:
                    provider_vector_store_file = provider_vector_store_files_by_external_file_id.get(upload.external_file_id)

            result_items.append(
                {
                    "include_order": include_order,
                    "file": rag_file,
                    "provider_upload": provider_upload,
                    "provider_vector_store_file": provider_vector_store_file,
                }
            )

        return {
            "provider_type": rag_index.provider_type,
            "vector_store_id": vector_store_id,
            "items": result_items,
            "errors": errors,
        }

    def _extract_provider_file_id(self, item: dict) -> str | None:
        file_id = item.get("file_id")
        if isinstance(file_id, str) and file_id:
            return file_id

        nested = item.get("file")
        if isinstance(nested, dict):
            nested_id = nested.get("id") or nested.get("file_id")
            if isinstance(nested_id, str) and nested_id:
                return nested_id

        return None
