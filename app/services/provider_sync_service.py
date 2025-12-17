from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
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
_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()


logger = logging.getLogger(__name__)


class ProviderSyncService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._config = get_config()

    def _dump_payload(self, payload: object) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            return str(payload)

    def _redact_headers(self, headers: dict | None) -> dict:
        if not headers:
            return {}

        redacted: dict = {}
        for k, v in headers.items():
            key = str(k)
            low = key.lower()
            if low in {"authorization", "proxy-authorization", "x-api-key", "api-key"}:
                redacted[key] = "***"
            else:
                redacted[key] = v
        return redacted

    def _log_http_error(self, *, event: str, provider_type: str, payload: dict, error: Exception) -> None:
        req = getattr(error, "request", None)
        resp = getattr(error, "response", None)

        req_info: dict[str, object] | None = None
        if req is not None:
            req_info = {
                "method": getattr(req, "method", None),
                "url": str(getattr(req, "url", "")),
                "headers": self._redact_headers(dict(getattr(req, "headers", {}) or {})),
                "body": None,
            }
            try:
                body = getattr(req, "content", None)
                if body:
                    req_info["body"] = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body)
            except Exception:
                req_info["body"] = None

        resp_info: dict[str, object] | None = None
        if resp is not None:
            resp_info = {
                "status_code": getattr(resp, "status_code", None),
                "headers": self._redact_headers(dict(getattr(resp, "headers", {}) or {})),
                "body": None,
            }
            try:
                body_text = getattr(resp, "text", None)
                if body_text:
                    resp_info["body"] = body_text
                else:
                    body_bytes = getattr(resp, "content", None)
                    if body_bytes:
                        resp_info["body"] = (
                            body_bytes.decode("utf-8", errors="replace")
                            if isinstance(body_bytes, (bytes, bytearray))
                            else str(body_bytes)
                        )
            except Exception:
                resp_info["body"] = None

        logger.warning(
            "provider_sync http_error event=%s provider=%s payload=%s request=%s response=%s error=%s",
            event,
            provider_type,
            self._dump_payload(payload),
            self._dump_payload(req_info) if req_info is not None else None,
            self._dump_payload(resp_info) if resp_info is not None else None,
            repr(error),
        )

    def sync(self, provider_type: str) -> dict:
        default_domain_id = self._config.default_domain_id
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)

        domains_used: set[str] = set()
        vector_store_domain_by_id: dict[str, str] = {}
        vector_store_files_by_id: dict[str, list[dict]] = {}

        report: dict = {
            "provider_type": provider_type,
            "domain_id": default_domain_id,
            "default_domain_id": default_domain_id,
            "domains_used": [],
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
        provider_vector_store_payloads: dict[str, dict] = {}

        for vs in vector_stores:
            vs_id = vs.get("id")
            if not vs_id:
                continue
            vs_id = str(vs_id)
            provider_vs_ids.add(vs_id)

            vs_payload: dict = vs if isinstance(vs, dict) else {"id": vs_id}
            try:
                vs_detail = provider.retrieve_vector_store(vs_id)
                if isinstance(vs_detail, dict):
                    vs_payload = vs_detail
                    provider_vector_store_payloads[vs_id] = vs_detail
                    logger.info(
                        "provider_sync retrieve_vector_store provider=%s vector_store_id=%s payload=%s",
                        provider_type,
                        vs_id,
                        self._dump_payload(vs_detail),
                    )
            except Exception as e:
                logger.warning(
                    "provider_sync retrieve_vector_store_failed provider=%s vector_store_id=%s error=%s",
                    provider_type,
                    vs_id,
                    repr(e),
                )

            try:
                domain_id_for_index: str | None = None
                indexes = (
                    self._db.query(RagIndex)
                    .filter(RagIndex.provider_type == provider_type)
                    .filter(RagIndex.external_id == vs_id)
                    .all()
                )
                rag_index = indexes[0] if indexes else None
                if len(indexes) > 1:
                    report["errors"].append(
                        f"vector_store={vs_id}: найдено несколько локальных индексов с одинаковым external_id (count={len(indexes)})"
                    )

                if rag_index is not None:
                    domain_id_for_index = rag_index.domain_id

                if domain_id_for_index is None:
                    try:
                        items = provider.list_vector_store_files(
                            vs_id,
                            limit=_DEFAULT_LIST_LIMIT,
                        )
                        logger.info(
                            "provider_sync list_vector_store_files provider=%s vector_store_id=%s payload=%s",
                            provider_type,
                            vs_id,
                            self._dump_payload(items),
                        )
                        if isinstance(items, list):
                            vector_store_files_by_id[vs_id] = items
                    except Exception as e:
                        report["errors"].append(f"vector_store={vs_id}: ошибка получения списка файлов для определения домена: {e}")

                    inferred_domains: set[str] = set()
                    for item in vector_store_files_by_id.get(vs_id, []):
                        vector_store_file_id = item.get("id")
                        external_file_id = self._extract_external_file_id(item)
                        if vector_store_file_id and (not external_file_id or "file_id" not in item):
                            try:
                                vs_file = provider.retrieve_vector_store_file(vs_id, str(vector_store_file_id))
                                extracted = self._extract_external_file_id(vs_file if isinstance(vs_file, dict) else None)
                                if extracted:
                                    external_file_id = extracted
                            except Exception:
                                pass

                        if not external_file_id:
                            continue
                        external_file_id = str(external_file_id)

                        upload = (
                            self._db.query(RagProviderFileUpload)
                            .filter(RagProviderFileUpload.provider_id == provider_type)
                            .filter(RagProviderFileUpload.external_file_id == external_file_id)
                            .order_by(RagProviderFileUpload.created_at.desc())
                            .first()
                        )
                        if upload is None:
                            continue

                        rag_file = self._db.query(RagFile).filter(RagFile.id == upload.local_file_id).one_or_none()
                        if rag_file is None:
                            continue

                        inferred_domains.add(rag_file.domain_id)
                        if len(inferred_domains) > 1:
                            break

                    if len(inferred_domains) == 1:
                        domain_id_for_index = next(iter(inferred_domains))
                    elif len(inferred_domains) > 1:
                        report["errors"].append(
                            f"vector_store={vs_id}: не удалось однозначно определить домен (файлы из разных доменов: {sorted(inferred_domains)})"
                        )

                        vector_store_domain_by_id[vs_id] = "__ambiguous__"
                        continue

                if domain_id_for_index is None:
                    domain_id_for_index = default_domain_id

                vector_store_domain_by_id[vs_id] = domain_id_for_index
                domains_used.add(domain_id_for_index)

                if rag_index is None:
                    provider_status = vs_payload.get("status") if isinstance(vs_payload, dict) else None
                    if not isinstance(provider_status, str) or not provider_status:
                        provider_status = "not_indexed"

                    provider_created_at = vs_payload.get("created_at") if isinstance(vs_payload, dict) else None
                    indexed_at: datetime | None = None
                    if isinstance(provider_created_at, (int, float)):
                        indexed_at = datetime.utcfromtimestamp(provider_created_at)

                    metadata: dict | None = None
                    if isinstance(vs_payload, dict):
                        metadata = {}
                        provider_meta = vs_payload.get("metadata")
                        if isinstance(provider_meta, dict):
                            metadata.update(provider_meta)
                        metadata["provider_payload"] = vs_payload

                    rag_index = RagIndex(
                        id=str(uuid4()),
                        domain_id=domain_id_for_index,
                        provider_type=provider_type,
                        external_id=vs_id,
                        name=vs_payload.get("name"),
                        description=vs_payload.get("description"),
                        expires_after=vs_payload.get("expires_after"),
                        file_ids=None,
                        metadata_=metadata,
                        indexing_status=str(provider_status),
                        indexed_at=indexed_at,
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
                        ("expires_after", "expires_after"),
                    ):
                        if src_key in vs_payload and getattr(rag_index, attr_name) != vs_payload.get(src_key):
                            setattr(rag_index, attr_name, vs_payload.get(src_key))
                            changed = True

                    if isinstance(vs_payload, dict):
                        current_meta = rag_index.metadata_ if isinstance(rag_index.metadata_, dict) else {}
                        provider_meta = vs_payload.get("metadata")
                        if isinstance(provider_meta, dict):
                            for k, v in provider_meta.items():
                                if current_meta.get(k) != v:
                                    current_meta[k] = v
                                    changed = True

                        if current_meta.get("provider_payload") != vs_payload:
                            current_meta["provider_payload"] = vs_payload
                            changed = True

                        if changed:
                            rag_index.metadata_ = current_meta

                        provider_status = vs_payload.get("status")
                        if isinstance(provider_status, str) and provider_status and rag_index.indexing_status != provider_status:
                            rag_index.indexing_status = provider_status
                            changed = True

                        provider_created_at = vs_payload.get("created_at")
                        if isinstance(provider_created_at, (int, float)):
                            indexed_at = datetime.utcfromtimestamp(provider_created_at)
                            if rag_index.indexed_at != indexed_at:
                                rag_index.indexed_at = indexed_at
                                changed = True

                    if changed:
                        self._db.commit()
                        self._db.refresh(rag_index)
                        report["indexes_updated"] += 1

            except Exception as e:
                report["errors"].append(f"vector_store={vs_id}: ошибка синхронизации индекса: {e}")

        local_indexes = (
            self._db.query(RagIndex)
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
            .filter(RagIndex.provider_type == provider_type)
            .filter(RagIndex.external_id.isnot(None))
            .all()
        ):
            if rag_index.external_id:
                if rag_index.external_id in indexes_by_external_id:
                    report["errors"].append(
                        f"vector_store={rag_index.external_id}: найдено несколько RagIndex с одинаковым external_id в разных доменах"
                    )
                    continue
                indexes_by_external_id[rag_index.external_id] = rag_index

        for vs_id in provider_vs_ids:
            if vector_store_domain_by_id.get(vs_id) == "__ambiguous__":
                continue
            rag_index = indexes_by_external_id.get(vs_id)
            if rag_index is None:
                continue

            domain_id_for_index = vector_store_domain_by_id.get(vs_id) or rag_index.domain_id
            domains_used.add(domain_id_for_index)

            try:
                vs_payload = provider_vector_store_payloads.get(vs_id)
                if vs_payload is None:
                    vs_detail = provider.retrieve_vector_store(vs_id)
                    if isinstance(vs_detail, dict):
                        vs_payload = vs_detail
                        logger.info(
                            "provider_sync retrieve_vector_store provider=%s vector_store_id=%s payload=%s",
                            provider_type,
                            vs_id,
                            self._dump_payload(vs_detail),
                        )
            except Exception as e:
                logger.warning(
                    "provider_sync retrieve_vector_store_failed provider=%s vector_store_id=%s error=%s",
                    provider_type,
                    vs_id,
                    repr(e),
                )

            try:
                if vs_id in vector_store_files_by_id:
                    items = vector_store_files_by_id[vs_id]
                else:
                    items = provider.list_vector_store_files(
                        vs_id,
                        limit=_DEFAULT_LIST_LIMIT,
                    )
                    logger.info(
                        "provider_sync list_vector_store_files provider=%s vector_store_id=%s payload=%s",
                        provider_type,
                        vs_id,
                        self._dump_payload(items),
                    )
                    if isinstance(items, list):
                        vector_store_files_by_id[vs_id] = items
            except Exception as e:
                report["errors"].append(f"vector_store={vs_id}: ошибка получения списка файлов: {e}")
                continue

            local_file_ids_for_index: list[str] = []
            skipped_items = 0

            for pos, item in enumerate(items, start=1):
                vector_store_file_id = item.get("id")
                external_file_id = self._extract_external_file_id(item)
                vector_store_file_meta: dict | None = None
                if vector_store_file_id and (not external_file_id or "file_id" not in item):
                    try:
                        vs_file = provider.retrieve_vector_store_file(vs_id, str(vector_store_file_id))
                        logger.info(
                            "provider_sync retrieve_vector_store_file provider=%s vector_store_id=%s vector_store_file_id=%s payload=%s",
                            provider_type,
                            vs_id,
                            str(vector_store_file_id),
                            self._dump_payload(vs_file),
                        )
                        vector_store_file_meta = vs_file if isinstance(vs_file, dict) else None
                        extracted = self._extract_external_file_id(vs_file)
                        if extracted:
                            external_file_id = extracted
                    except Exception as e:
                        logger.warning(
                            "provider_sync retrieve_vector_store_file_failed provider=%s vector_store_id=%s vector_store_file_id=%s error=%s",
                            provider_type,
                            vs_id,
                            str(vector_store_file_id),
                            repr(e),
                        )

                if not external_file_id:
                    report["errors"].append(
                        f"vector_store={vs_id}: не удалось определить внешний file_id для элемента списка (id={vector_store_file_id})"
                    )
                    skipped_items += 1
                    continue
                external_file_id = str(external_file_id)

                try:
                    uploads = (
                        self._db.query(RagProviderFileUpload)
                        .filter(RagProviderFileUpload.provider_id == provider_type)
                        .filter(RagProviderFileUpload.external_file_id == external_file_id)
                        .order_by(RagProviderFileUpload.created_at.desc())
                        .all()
                    )
                    upload = uploads[0] if uploads else None
                    if len(uploads) > 1:
                        report["errors"].append(
                            f"vector_store={vs_id} external_file_id={external_file_id}: найдено несколько записей rag_provider_file_uploads (count={len(uploads)})"
                        )

                    rag_file: RagFile | None = None
                    if upload is not None:
                        rag_file = self._db.query(RagFile).filter(RagFile.id == upload.local_file_id).one_or_none()
                        if rag_file is not None and rag_file.domain_id != domain_id_for_index:
                            report["errors"].append(
                                f"vector_store={vs_id} external_file_id={external_file_id}: найден локальный файл в другом домене (file_id={rag_file.id}, domain_id={rag_file.domain_id}, expected_domain_id={domain_id_for_index})"
                            )
                            continue

                    provider_meta: dict | None = None
                    try:
                        provider_meta = provider.retrieve_file(external_file_id)
                    except Exception:
                        provider_meta = vector_store_file_meta

                    provider_status = self._provider_file_status(provider_meta) or "unknown"

                    provider_bytes: bytes | None = None
                    files_api_error: Exception | None = None
                    try:
                        provider_bytes = provider.retrieve_file_content(external_file_id)
                    except Exception as e:
                        files_api_error = e
                        self._log_http_error(
                            event="retrieve_file_content",
                            provider_type=provider_type,
                            payload={
                                "external_file_id": external_file_id,
                                "vector_store_id": vs_id,
                                "vector_store_file_id": vector_store_file_id,
                                "request_body": None,
                            },
                            error=e,
                        )

                    if provider_bytes is None:
                        tried_ids: list[str] = []
                        if vector_store_file_id:
                            tried_ids.append(str(vector_store_file_id))
                        if external_file_id and str(external_file_id) not in tried_ids:
                            tried_ids.append(str(external_file_id))

                        last_error: Exception | None = None
                        for vs_file_id_for_content in tried_ids:
                            try:
                                content_items = provider.retrieve_vector_store_file_content(vs_id, vs_file_id_for_content)
                                provider_bytes = self._vector_store_file_content_to_bytes(content_items)
                                last_error = None
                                break
                            except Exception as e:
                                last_error = e
                                self._log_http_error(
                                    event="retrieve_vector_store_file_content",
                                    provider_type=provider_type,
                                    payload={
                                        "vector_store_id": vs_id,
                                        "vector_store_file_id": vs_file_id_for_content,
                                        "request_body": None,
                                    },
                                    error=e,
                                )

                    provider_sha256: str | None = None
                    content_error: Exception | None = None
                    if provider_bytes is None:
                        content_error = last_error or files_api_error
                    else:
                        provider_sha256 = self._calc_sha256_bytes(provider_bytes)

                    local_sha256: str | None = None
                    if rag_file is not None:
                        local_path = Path(rag_file.local_path)
                        if local_path.exists():
                            try:
                                local_sha256 = self._calc_sha256_file(local_path)
                            except Exception as e:
                                report["errors"].append(
                                    f"file_id={rag_file.id}: ошибка вычисления sha256 локального файла: {e}"
                                )
                        else:
                            if provider_bytes is not None:
                                self._write_bytes(local_path, provider_bytes)
                                rag_file.size_bytes = len(provider_bytes)
                                self._db.commit()
                                local_sha256 = provider_sha256
                            else:
                                report["errors"].append(
                                    f"file_id={rag_file.id}: локальный файл отсутствует на диске и провайдер не вернул контент"
                                )

                    if rag_file is None:
                        file_name = self._provider_file_name(external_file_id=external_file_id, provider_meta=provider_meta)
                        file_type = self._guess_file_type(file_name)

                        new_local_file_id = str(uuid4())
                        local_path = self._make_local_file_path(
                            domain_id=domain_id_for_index,
                            local_file_id=new_local_file_id,
                            file_name=file_name,
                        )

                        if provider_bytes is not None:
                            self._write_bytes(local_path, provider_bytes)

                        rag_file = RagFile(
                            id=new_local_file_id,
                            domain_id=domain_id_for_index,
                            file_name=file_name,
                            file_type=file_type,
                            local_path=str(local_path),
                            size_bytes=len(provider_bytes) if provider_bytes is not None else 0,
                            chunking_strategy=None,
                            tags=None,
                            notes=None,
                        )
                        self._db.add(rag_file)
                        self._db.commit()
                        self._db.refresh(rag_file)
                        report["files_created"] += 1
                        action = "created"
                        if provider_sha256 is not None:
                            local_sha256 = provider_sha256

                        if upload is not None and upload.local_file_id != rag_file.id:
                            upload.local_file_id = rag_file.id
                            self._db.commit()
                    else:
                        report["files_kept"] += 1
                        action = "kept"

                    if local_sha256 is not None and provider_sha256 is not None and local_sha256 != provider_sha256:
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

                    local_file_ids_for_index.append(rag_file.id)

                    if upload is None:
                        upload = RagProviderFileUpload(
                            id=str(uuid4()),
                            provider_id=provider_type,
                            local_file_id=rag_file.id,
                            external_file_id=external_file_id,
                            external_uploaded_at=self._provider_uploaded_at(provider_meta),
                            content_sha256=local_sha256 or provider_sha256 or _EMPTY_CONTENT_SHA256,
                            status=provider_status,
                            last_error=repr(content_error) if content_error is not None else None,
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
                        if new_sha is not None and upload.content_sha256 != new_sha:
                            upload.content_sha256 = new_sha
                            changed = True
                        if upload.status != provider_status:
                            upload.status = provider_status
                            changed = True
                        if (repr(content_error) if content_error is not None else None) != upload.last_error:
                            upload.last_error = repr(content_error) if content_error is not None else None
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
                            "byte_mismatch": bool(
                                local_sha256 is not None
                                and provider_sha256 is not None
                                and local_sha256 != provider_sha256
                            ),
                            "content_available": bool(provider_bytes is not None),
                        }
                    )

                except Exception as e:
                    report["errors"].append(
                        f"vector_store={vs_id} external_file_id={external_file_id}: ошибка синхронизации файла: {e}"
                    )

            expected_count = len(items) if isinstance(items, list) else 0
            processed_count = len(local_file_ids_for_index)
            logger.info(
                "provider_sync index_files_summary provider=%s vector_store_id=%s expected=%s processed=%s skipped=%s",
                provider_type,
                vs_id,
                expected_count,
                processed_count,
                skipped_items,
            )

            if expected_count == processed_count:
                try:
                    deleted = (
                        self._db.query(RagIndexFile)
                        .filter(RagIndexFile.index_id == rag_index.id)
                        .filter(~RagIndexFile.file_id.in_(set(local_file_ids_for_index) or {""}))
                        .delete(synchronize_session=False)
                    )
                    report["index_files_deleted"] += int(deleted or 0)

                    if rag_index.file_ids != local_file_ids_for_index:
                        rag_index.file_ids = local_file_ids_for_index

                    self._db.commit()
                except Exception as e:
                    report["errors"].append(f"vector_store={vs_id}: ошибка финализации rag_index_files/file_ids: {e}")
            else:
                logger.warning(
                    "provider_sync index_files_incomplete provider=%s vector_store_id=%s expected=%s processed=%s skipped=%s",
                    provider_type,
                    vs_id,
                    expected_count,
                    processed_count,
                    skipped_items,
                )

        report["domains_used"] = sorted(domains_used)
        return report

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

        val = obj.get("id")
        if isinstance(val, str) and val:
            return val

        return None

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

    def _provider_file_status(self, provider_meta: dict | None) -> str | None:
        if not provider_meta:
            return None

        status = provider_meta.get("status")
        if isinstance(status, str) and status:
            return status

        file_obj = provider_meta.get("file")
        if isinstance(file_obj, dict):
            status = file_obj.get("status")
            if isinstance(status, str) and status:
                return status

        return None

    def _provider_file_name(self, *, external_file_id: str, provider_meta: dict | None) -> str:
        if provider_meta and isinstance(provider_meta.get("filename"), str) and provider_meta.get("filename"):
            return Path(provider_meta["filename"]).name
        if provider_meta and isinstance(provider_meta.get("file"), dict):
            f = provider_meta["file"]
            if isinstance(f.get("filename"), str) and f.get("filename"):
                return Path(f["filename"]).name
            if isinstance(f.get("name"), str) and f.get("name"):
                return Path(f["name"]).name
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
