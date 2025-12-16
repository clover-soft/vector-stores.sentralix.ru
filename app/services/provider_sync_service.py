from __future__ import annotations

from datetime import datetime
import hashlib
import mimetypes
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from config import get_config
from models.rag_file import RagFile
from models.rag_index import RagIndex
from models.rag_index_file import RagIndexFile
from models.rag_provider_file_upload import RagProviderFileUpload
from services.providers_connections_service import ProvidersConnectionsService


_DEFAULT_LIST_LIMIT = 1000
_CHUNK_SIZE_BYTES = 1024 * 1024


class ProviderSyncService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._config = get_config()

    def sync(self, provider_type: str) -> dict:
        domain_id = self._config.default_domain_id
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)

        report: dict = {
            "provider_type": provider_type,
            "domain_id": domain_id,
            "indexes_created": 0,
            "indexes_updated": 0,
            "indexes_detached": 0,
            "files_created": 0,
            "files_kept": 0,
            "index_files_created": 0,
            "index_files_deleted": 0,
            "provider_uploads_created": 0,
            "provider_uploads_deleted": 0,
            "file_results": [],
            "files_byte_mismatches": [],
            "errors": [],
        }

        vector_stores = provider.list_vector_stores(limit=_DEFAULT_LIST_LIMIT)
        provider_vs_ids: set[str] = set()

        for vs in vector_stores:
            vs_id = vs.get("id")
            if not vs_id:
                continue
            provider_vs_ids.add(str(vs_id))

            try:
                rag_index = (
                    self._db.query(RagIndex)
                    .filter(RagIndex.domain_id == domain_id)
                    .filter(RagIndex.provider_type == provider_type)
                    .filter(RagIndex.external_id == str(vs_id))
                    .one_or_none()
                )

                if rag_index is None:
                    rag_index = RagIndex(
                        id=str(uuid4()),
                        domain_id=domain_id,
                        provider_type=provider_type,
                        external_id=str(vs_id),
                        name=vs.get("name"),
                        description=vs.get("description"),
                        chunking_strategy=vs.get("chunking_strategy"),
                        expires_after=vs.get("expires_after"),
                        file_ids=vs.get("file_ids") if isinstance(vs.get("file_ids"), list) else None,
                        metadata_=vs.get("metadata") if isinstance(vs.get("metadata"), dict) else None,
                        indexing_status="not_indexed",
                    )
                    self._db.add(rag_index)
                    self._db.commit()
                    self._db.refresh(rag_index)
                    report["indexes_created"] += 1
                else:
                    changed = False
                    for attr_name, src_key in (
                        ("name", "name"),
                        ("description", "description"),
                        ("chunking_strategy", "chunking_strategy"),
                        ("expires_after", "expires_after"),
                    ):
                        if src_key in vs and getattr(rag_index, attr_name) != vs.get(src_key):
                            setattr(rag_index, attr_name, vs.get(src_key))
                            changed = True

                    if "metadata" in vs and isinstance(vs.get("metadata"), dict) and rag_index.metadata_ != vs.get("metadata"):
                        rag_index.metadata_ = vs.get("metadata")
                        changed = True

                    if changed:
                        self._db.commit()
                        self._db.refresh(rag_index)
                        report["indexes_updated"] += 1

            except Exception as e:
                report["errors"].append(f"vector_store={vs_id}: ошибка синхронизации индекса: {e}")

        local_indexes = (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == domain_id)
            .filter(RagIndex.provider_type == provider_type)
            .filter(RagIndex.external_id.isnot(None))
            .all()
        )

        for rag_index in local_indexes:
            if not rag_index.external_id:
                continue
            if rag_index.external_id in provider_vs_ids:
                continue

            try:
                file_ids = [
                    row.file_id
                    for row in self._db.query(RagIndexFile.file_id)
                    .filter(RagIndexFile.index_id == rag_index.id)
                    .all()
                ]

                deleted_uploads = 0
                if file_ids:
                    deleted_uploads = (
                        self._db.query(RagProviderFileUpload)
                        .filter(RagProviderFileUpload.provider_id == provider_type)
                        .filter(RagProviderFileUpload.local_file_id.in_(file_ids))
                        .delete(synchronize_session=False)
                    )

                rag_index.external_id = None
                self._db.commit()
                report["indexes_detached"] += 1
                report["provider_uploads_deleted"] += int(deleted_uploads or 0)
            except Exception as e:
                report["errors"].append(f"index_id={rag_index.id}: ошибка отвязки external_id и чистки загрузок: {e}")

        indexes_by_external_id: dict[str, RagIndex] = {}
        for rag_index in (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == domain_id)
            .filter(RagIndex.provider_type == provider_type)
            .filter(RagIndex.external_id.isnot(None))
            .all()
        ):
            if rag_index.external_id:
                indexes_by_external_id[rag_index.external_id] = rag_index

        for vs_id in provider_vs_ids:
            rag_index = indexes_by_external_id.get(vs_id)
            if rag_index is None:
                continue

            try:
                items = provider.list_vector_store_files(
                    vs_id,
                    limit=_DEFAULT_LIST_LIMIT,
                )
            except Exception as e:
                report["errors"].append(f"vector_store={vs_id}: ошибка получения списка файлов: {e}")
                continue

            for pos, item in enumerate(items, start=1):
                vector_store_file_id = item.get("id")
                external_file_id = item.get("file_id")
                vector_store_file_meta: dict | None = None
                if not external_file_id and vector_store_file_id:
                    try:
                        vs_file = provider.retrieve_vector_store_file(vs_id, str(vector_store_file_id))
                        vector_store_file_meta = vs_file if isinstance(vs_file, dict) else None
                        external_file_id = vs_file.get("file_id") or vs_file.get("id")
                    except Exception:
                        external_file_id = None

                if not external_file_id:
                    report["errors"].append(
                        f"vector_store={vs_id}: не удалось определить внешний file_id для элемента списка (id={vector_store_file_id})"
                    )
                    continue
                external_file_id = str(external_file_id)

                try:
                    rag_file = (
                        self._db.query(RagFile)
                        .filter(RagFile.domain_id == domain_id)
                        .filter(RagFile.external_file_id == external_file_id)
                        .one_or_none()
                    )

                    try:
                        provider_bytes = provider.retrieve_file_content(external_file_id)
                    except Exception as e:
                        vs_file_id_for_content = str(vector_store_file_id or external_file_id)
                        try:
                            content_items = provider.retrieve_vector_store_file_content(vs_id, vs_file_id_for_content)
                            provider_bytes = self._vector_store_file_content_to_bytes(content_items)
                        except Exception:
                            raise e
                    provider_sha256 = self._calc_sha256_bytes(provider_bytes)

                    provider_meta: dict | None = None
                    try:
                        provider_meta = provider.retrieve_file(external_file_id)
                    except Exception:
                        provider_meta = vector_store_file_meta

                    if rag_file is None:
                        file_name = self._provider_file_name(external_file_id=external_file_id, provider_meta=provider_meta)
                        file_type = self._guess_file_type(file_name)

                        new_local_file_id = str(uuid4())
                        local_path = self._make_local_file_path(
                            domain_id=domain_id,
                            local_file_id=new_local_file_id,
                            file_name=file_name,
                        )
                        self._write_bytes(local_path, provider_bytes)

                        external_uploaded_at = self._provider_uploaded_at(provider_meta)

                        rag_file = RagFile(
                            id=new_local_file_id,
                            domain_id=domain_id,
                            file_name=file_name,
                            file_type=file_type,
                            local_path=str(local_path),
                            size_bytes=len(provider_bytes),
                            external_file_id=external_file_id,
                            external_uploaded_at=external_uploaded_at,
                            chunking_strategy=None,
                            tags=None,
                            notes=None,
                        )
                        self._db.add(rag_file)
                        self._db.commit()
                        self._db.refresh(rag_file)
                        report["files_created"] += 1
                        action = "created"
                        local_sha256 = provider_sha256
                    else:
                        report["files_kept"] += 1
                        action = "kept"
                        local_sha256 = None
                        try:
                            local_sha256 = self._calc_sha256_file(Path(rag_file.local_path))
                        except Exception as e:
                            report["errors"].append(f"file_id={rag_file.id}: ошибка вычисления sha256 локального файла: {e}")

                    if local_sha256 is not None and local_sha256 != provider_sha256:
                        mismatch = {
                            "vector_store_id": vs_id,
                            "external_file_id": external_file_id,
                            "local_file_id": rag_file.id,
                            "local_sha256": local_sha256,
                            "provider_sha256": provider_sha256,
                            "local_path": rag_file.local_path,
                        }
                        report["files_byte_mismatches"].append(mismatch)

                    link = (
                        self._db.query(RagIndexFile)
                        .filter(RagIndexFile.index_id == rag_index.id)
                        .filter(RagIndexFile.file_id == rag_file.id)
                        .one_or_none()
                    )
                    if link is None:
                        link = RagIndexFile(index_id=rag_index.id, file_id=rag_file.id, include_order=pos)
                        self._db.add(link)
                        self._db.commit()
                        report["index_files_created"] += 1
                    else:
                        if link.include_order != pos:
                            link.include_order = pos
                            self._db.commit()

                    upload = (
                        self._db.query(RagProviderFileUpload)
                        .filter(RagProviderFileUpload.provider_id == provider_type)
                        .filter(RagProviderFileUpload.local_file_id == rag_file.id)
                        .one_or_none()
                    )

                    if upload is None:
                        upload = RagProviderFileUpload(
                            id=str(uuid4()),
                            provider_id=provider_type,
                            local_file_id=rag_file.id,
                            external_file_id=external_file_id,
                            external_uploaded_at=self._provider_uploaded_at(provider_meta),
                            content_sha256=local_sha256 or provider_sha256,
                            status="uploaded",
                            last_error=None,
                            raw_provider_json=provider_meta,
                        )
                        self._db.add(upload)
                        self._db.commit()
                        self._db.refresh(upload)
                        report["provider_uploads_created"] += 1
                    else:
                        changed = False
                        if upload.external_file_id != external_file_id:
                            upload.external_file_id = external_file_id
                            changed = True
                        new_dt = self._provider_uploaded_at(provider_meta)
                        if new_dt is not None and upload.external_uploaded_at != new_dt:
                            upload.external_uploaded_at = new_dt
                            changed = True
                        new_sha = local_sha256 or provider_sha256
                        if upload.content_sha256 != new_sha:
                            upload.content_sha256 = new_sha
                            changed = True
                        if upload.status != "uploaded":
                            upload.status = "uploaded"
                            changed = True
                        if provider_meta is not None and upload.raw_provider_json != provider_meta:
                            upload.raw_provider_json = provider_meta
                            changed = True
                        if changed:
                            self._db.commit()

                    report["file_results"].append(
                        {
                            "vector_store_id": vs_id,
                            "external_file_id": external_file_id,
                            "local_file_id": rag_file.id,
                            "action": action,
                            "local_sha256": local_sha256,
                            "provider_sha256": provider_sha256,
                            "byte_mismatch": bool(local_sha256 is not None and local_sha256 != provider_sha256),
                        }
                    )

                except Exception as e:
                    report["errors"].append(
                        f"vector_store={vs_id} external_file_id={external_file_id}: ошибка синхронизации файла: {e}"
                    )

        return report

    def _vector_store_file_content_to_bytes(self, items: list[dict] | None) -> bytes:
        if not items:
            raise ValueError("Провайдер вернул пустой контент файла")

        parts: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
                continue
            if isinstance(text, dict) and isinstance(text.get("value"), str) and text.get("value"):
                parts.append(text["value"])
                continue

            content = item.get("content")
            if isinstance(content, str) and content:
                parts.append(content)
                continue

            data = item.get("data")
            if isinstance(data, str) and data:
                parts.append(data)
                continue

        if parts:
            return "\n".join(parts).encode("utf-8")

        return str(items).encode("utf-8")

    def _make_local_file_path(self, *, domain_id: str, local_file_id: str, file_name: str) -> Path:
        safe_name = Path(file_name).name
        return (
            Path(self._config.files_root)
            / domain_id
            / local_file_id
            / "original"
            / safe_name
        )

    def _write_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def _provider_uploaded_at(self, provider_meta: dict | None) -> datetime | None:
        if not provider_meta:
            return None
        created_at = provider_meta.get("created_at")
        if isinstance(created_at, (int, float)):
            return datetime.utcfromtimestamp(created_at)
        return None

    def _provider_file_name(self, *, external_file_id: str, provider_meta: dict | None) -> str:
        if provider_meta and isinstance(provider_meta.get("filename"), str) and provider_meta.get("filename"):
            return Path(provider_meta["filename"]).name
        return external_file_id

    def _guess_file_type(self, file_name: str) -> str:
        guessed, _ = mimetypes.guess_type(file_name)
        return guessed or "application/octet-stream"

    def _calc_sha256_bytes(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _calc_sha256_file(self, path: Path) -> str:
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
