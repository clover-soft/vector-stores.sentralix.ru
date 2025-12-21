from __future__ import annotations

import hashlib
from models.rag_index_file import RagIndexFile
from models.rag_provider_file_upload import RagProviderFileUpload
from pathlib import Path
from sqlalchemy.orm import Session

from services.index_files_service import IndexFilesService
from services.indexes_service import IndexesService
from services.provider_file_uploads_service import ProviderFileUploadsService
from services.providers_connections_service import ProvidersConnectionsService

_DEFAULT_LIST_LIMIT = 1000
_CHUNK_SIZE_BYTES = 1024 * 1024


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
        dry_run: bool = False,
    ) -> dict:
        indexes_service = IndexesService(db=self._db, domain_id=self._domain_id)
        rag_index = indexes_service.get_index(index_id)
        if rag_index is None:
            raise ValueError("Индекс не найден")

        provider_type = rag_index.provider_type
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)

        errors: list[str] = []

        had_external_id = bool(rag_index.external_id)

        created_vector_store = False
        will_create_vector_store = (not had_external_id)

        if not rag_index.external_id:
            if dry_run:
                vector_store_id = None
            else:
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
        missing_upload_local_file_ids: list[str] = []
        upload_by_local_file_id: dict[str, object] = {}

        if dry_run:
            for _, rag_file in rows:
                upload = self._get_existing_upload(
                    provider_type=provider_type,
                    local_file_id=rag_file.id,
                )
                if upload is None:
                    missing_upload_local_file_ids.append(rag_file.id)
                    continue

                if force_upload:
                    missing_upload_local_file_ids.append(rag_file.id)
                    continue

                sha256 = self._calc_sha256(Path(rag_file.local_path))
                if upload.content_sha256 != sha256:
                    missing_upload_local_file_ids.append(rag_file.id)
                    continue

                uploads.append(upload)
                upload_by_local_file_id[str(getattr(upload, "local_file_id", ""))] = upload
                if upload.external_file_id:
                    desired_provider_file_ids.add(str(upload.external_file_id))
        else:
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

        provider_vs_files: list[dict] = []
        if vector_store_id:
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
        
        # Получаем rag_index_files для доступа к external_id
        rag_index_files = (
            self._db.query(RagIndexFile)
            .filter(RagIndexFile.index_id == index_id)
            .all()
        )
        
        # Создаем отображение file_id -> rag_index_file
        index_file_by_local_file_id = {
            rif.file_id: rif for rif in rag_index_files
        }
        
        for _, rag_file in rows:
            index_file = index_file_by_local_file_id.get(rag_file.id)
            if not index_file or not index_file.external_id:
                continue
                
            # Используем chunking_strategy из rag_files (глобальный для файла)
            if isinstance(rag_file.chunking_strategy, dict):
                chunking_by_provider_file_id[index_file.external_id] = rag_file.chunking_strategy

        missing_provider_file_ids = desired_provider_file_ids - existing_provider_file_ids
        extra_provider_file_ids: set[str] = set()
        if detach_extra:
            extra_provider_file_ids = existing_provider_file_ids - desired_provider_file_ids

        desired_provider_file_ids_list = sorted(desired_provider_file_ids)
        existing_provider_file_ids_list = sorted(existing_provider_file_ids)
        missing_provider_file_ids_list = sorted(missing_provider_file_ids)
        extra_provider_file_ids_list = sorted(extra_provider_file_ids)

        attached_count = 0
        attach_results: list[dict] = []
        if (not dry_run) and missing_provider_file_ids:
            for provider_file_id in sorted(missing_provider_file_ids):
                try:
                    created = provider.attach_file_to_vector_store(
                        str(vector_store_id),
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
        if (not dry_run) and detach_extra:
            for provider_file_id in sorted(extra_provider_file_ids):
                vector_store_file_id = vector_store_file_id_by_provider_file_id.get(provider_file_id)
                if not vector_store_file_id:
                    continue

                try:
                    provider.detach_file_from_vector_store(str(vector_store_id), vector_store_file_id)
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
            "will_create_vector_store": will_create_vector_store,
            "dry_run": bool(dry_run),
            "uploads": uploads,
            "desired_provider_file_ids": desired_provider_file_ids_list,
            "existing_provider_file_ids": existing_provider_file_ids_list,
            "missing_provider_file_ids": missing_provider_file_ids_list,
            "extra_provider_file_ids": extra_provider_file_ids_list,
            "missing_upload_local_file_ids": sorted(set(missing_upload_local_file_ids)),
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

    def _get_existing_upload(self, *, provider_type: str, local_file_id: str) -> RagProviderFileUpload | None:
        return (
            self._db.query(RagProviderFileUpload)
            .filter(RagProviderFileUpload.provider_id == provider_type)
            .filter(RagProviderFileUpload.local_file_id == local_file_id)
            .one_or_none()
        )

    def _calc_sha256(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            raise ValueError("Файл отсутствует на диске")

        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

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
