from __future__ import annotations

from sqlalchemy.orm import Session

from services.index_files_service import IndexFilesService
from services.indexes_service import IndexesService
from services.provider_file_uploads_service import ProviderFileUploadsService
from services.providers_connections_service import ProvidersConnectionsService

_DEFAULT_LIST_LIMIT = 1000


class IndexPublishService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def publish(
        self,
        *,
        index_id: str,
        force_upload: bool = False,
        detach_extra: bool = True,
    ) -> dict:
        indexes_service = IndexesService(db=self._db, domain_id=self._domain_id)
        rag_index = indexes_service.get_index(index_id)
        if rag_index is None:
            raise ValueError("Индекс не найден")

        provider_type = rag_index.provider_type
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)

        errors: list[str] = []

        created_vector_store = False
        if not rag_index.external_id:
            provider_metadata = self._metadata_for_provider(rag_index.metadata_)
            created = provider.create_vector_store(
                name=rag_index.name,
                description=rag_index.description,
                expires_after=rag_index.expires_after,
                file_ids=None,
                metadata=provider_metadata,
            )
            vector_store_id = created.get("id")
            if not vector_store_id:
                raise ValueError("Провайдер не вернул id vector_store")

            rag_index.external_id = str(vector_store_id)
            self._db.commit()
            self._db.refresh(rag_index)
            created_vector_store = True
        else:
            vector_store_id = str(rag_index.external_id)

        index_files_service = IndexFilesService(db=self._db, domain_id=self._domain_id)
        rows = index_files_service.list_files(index_id=index_id)
        if rows is None:
            raise ValueError("Индекс не найден")

        uploads_service = ProviderFileUploadsService(db=self._db)
        uploads: list = []
        desired_provider_file_ids: set[str] = set()

        upload_by_local_file_id: dict[str, object] = {}

        for _, rag_file in rows:
            upload = uploads_service.get_or_sync(
                provider_type=provider_type,
                local_file_id=rag_file.id,
                force=force_upload,
                meta=None,
            )
            uploads.append(upload)
            upload_by_local_file_id[str(getattr(upload, "local_file_id", ""))] = upload
            if upload.external_file_id:
                desired_provider_file_ids.add(str(upload.external_file_id))

        provider_vs_files = provider.list_vector_store_files(
            vector_store_id,
            limit=_DEFAULT_LIST_LIMIT,
        )

        existing_provider_file_ids: set[str] = set()
        vector_store_file_id_by_provider_file_id: dict[str, str] = {}

        for item in provider_vs_files or []:
            if not isinstance(item, dict):
                continue

            vector_store_file_id = item.get("id")
            provider_file_id = self._extract_external_file_id(item)

            if (not provider_file_id) and vector_store_file_id:
                try:
                    detail = provider.retrieve_vector_store_file(vector_store_id, str(vector_store_file_id))
                    if isinstance(detail, dict):
                        provider_file_id = self._extract_external_file_id(detail)
                except Exception:
                    provider_file_id = None

            if not provider_file_id:
                continue

            provider_file_id = str(provider_file_id)
            existing_provider_file_ids.add(provider_file_id)
            if vector_store_file_id:
                vector_store_file_id_by_provider_file_id[provider_file_id] = str(vector_store_file_id)
        chunking_by_provider_file_id: dict[str, dict] = {}
        for _, rag_file in rows:
            upload = upload_by_local_file_id.get(rag_file.id)
            if not upload or not getattr(upload, "external_file_id", None):
                continue
            if isinstance(rag_file.chunking_strategy, dict):
                chunking_by_provider_file_id[str(upload.external_file_id)] = rag_file.chunking_strategy

        missing_provider_file_ids = desired_provider_file_ids - existing_provider_file_ids
        attached_count = 0
        attach_results: list[dict] = []
        if missing_provider_file_ids:
            for provider_file_id in sorted(missing_provider_file_ids):
                try:
                    created = provider.attach_file_to_vector_store(
                        vector_store_id,
                        file_id=provider_file_id,
                        chunking_strategy=chunking_by_provider_file_id.get(provider_file_id),
                    )
                    if isinstance(created, dict):
                        attach_results.append(created)
                    attached_count += 1
                except Exception as e:
                    errors.append(f"Не удалось прикрепить файл provider_file_id={provider_file_id}: {e}")

        batch_payload: dict | None = None

        detached_count = 0
        if detach_extra:
            extra_provider_file_ids = existing_provider_file_ids - desired_provider_file_ids
            for provider_file_id in sorted(extra_provider_file_ids):
                vector_store_file_id = vector_store_file_id_by_provider_file_id.get(provider_file_id)
                if not vector_store_file_id:
                    continue

                try:
                    provider.detach_file_from_vector_store(vector_store_id, vector_store_file_id)
                    detached_count += 1
                except Exception as e:
                    errors.append(
                        f"Не удалось открепить файл provider_file_id={provider_file_id} vector_store_file_id={vector_store_file_id}: {e}"
                    )

        return {
            "rag_index": rag_index,
            "provider_type": provider_type,
            "vector_store_id": vector_store_id,
            "created_vector_store": created_vector_store,
            "uploads": uploads,
            "attached_count": attached_count,
            "detached_count": detached_count,
            "batch": batch_payload,
            "attach_results": attach_results,
            "errors": errors,
        }

    def _metadata_for_provider(self, meta: dict | None) -> dict[str, str] | None:
        if not meta or not isinstance(meta, dict):
            return None

        out: dict[str, str] = {}
        for k, v in meta.items():
            if k == "provider_payload":
                continue
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v

        return out or None

    def _extract_external_file_id(self, obj: dict | None) -> str | None:
        if not obj or not isinstance(obj, dict):
            return None

        val = obj.get("file_id")
        if isinstance(val, str) and val:
            return val

        file_obj = obj.get("file")
        if isinstance(file_obj, str) and file_obj:
            return file_obj
        if isinstance(file_obj, dict):
            file_id = file_obj.get("id")
            if isinstance(file_id, str) and file_id:
                return file_id

            file_id = file_obj.get("file_id")
            if isinstance(file_id, str) and file_id:
                return file_id

            file_id = file_obj.get("fileId")
            if isinstance(file_id, str) and file_id:
                return file_id

        return None
