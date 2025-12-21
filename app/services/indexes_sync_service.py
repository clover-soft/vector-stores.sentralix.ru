from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models.rag_index import RagIndex
from services.providers_connections_service import ProvidersConnectionsService

_DEFAULT_LIST_LIMIT = 1000
_SYNC_SKIP_IF_DONE = True


class IndexesSyncService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id

    def sync_index(self, *, index_id: str, force: bool = False) -> dict:
        rag_index = (
            self._db.query(RagIndex)
            .filter(RagIndex.domain_id == self._domain_id)
            .filter(RagIndex.id == index_id)
            .one_or_none()
        )
        if rag_index is None:
            raise ValueError("Индекс не найден")

        return self._sync_rag_index(rag_index, force=force)

    def sync_domain_indexes(self, *, provider_type: str | None = None, force: bool = False) -> dict:
        q = self._db.query(RagIndex).filter(RagIndex.domain_id == self._domain_id)
        if provider_type is not None:
            q = q.filter(RagIndex.provider_type == provider_type)

        q = q.filter(RagIndex.external_id.isnot(None))

        items = q.order_by(RagIndex.created_at.desc()).all()

        updated: list[RagIndex] = []
        errors: list[str] = []

        for rag_index in items:
            try:
                self._sync_rag_index(rag_index, force=force)
                updated.append(rag_index)
            except Exception as e:
                errors.append(f"index_id={rag_index.id}: {e}")

        return {
            "items": updated,
            "errors": errors,
        }

    def _sync_rag_index(self, rag_index: RagIndex, *, force: bool) -> dict:
        if not rag_index.external_id:
            raise ValueError("У индекса нет external_id")

        if (
            (not force)
            and _SYNC_SKIP_IF_DONE
            and rag_index.indexing_status in {"completed"}
        ):
            report = {
                "provider_type": rag_index.provider_type,
                "vector_store_id": str(rag_index.external_id),
                "provider_files_count": 0,
                "aggregated_status": rag_index.indexing_status,
                "forced": False,
                "skipped": True,
            }
            return {
                "rag_index": rag_index,
                "sync_report": report,
            }

        provider_type = rag_index.provider_type
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        vector_store_id = str(rag_index.external_id)

        vector_store_payload = provider.retrieve_vector_store(vector_store_id)

        provider_files: list[dict] = []
        try:
            items = provider.list_vector_store_files(vector_store_id, limit=_DEFAULT_LIST_LIMIT)
            if isinstance(items, list):
                provider_files = [i for i in items if isinstance(i, dict)]
        except Exception:
            provider_files = []

        next_status = self._aggregate_status(vector_store_payload, provider_files)

        changed = False

        if isinstance(vector_store_payload, dict):
            current_meta = dict(rag_index.metadata_) if isinstance(rag_index.metadata_, dict) else {}
            if current_meta.get("provider_payload") != vector_store_payload:
                current_meta["provider_payload"] = vector_store_payload
                rag_index.metadata_ = current_meta
                changed = True

            # Устанавливаем expires_after из payload провайдера если он еще не установлен
            provider_expires_after = vector_store_payload.get("expires_after")
            if provider_expires_after is not None and rag_index.expires_after is None:
                rag_index.expires_after = provider_expires_after
                changed = True

        prev_status = rag_index.indexing_status
        if rag_index.indexing_status != next_status:
            rag_index.indexing_status = next_status
            changed = True

        if prev_status not in {"completed"} and next_status == "completed":
            rag_index.indexed_at = datetime.utcnow()
            changed = True

        if changed:
            self._db.commit()
            self._db.refresh(rag_index)

        report = {
            "provider_type": provider_type,
            "vector_store_id": vector_store_id,
            "provider_files_count": len(provider_files),
            "aggregated_status": next_status,
            "forced": bool(force),
            "skipped": False,
        }

        return {
            "rag_index": rag_index,
            "sync_report": report,
        }

    def _aggregate_status(self, vector_store_payload: object, provider_files: list[dict]) -> str:
        file_statuses: list[str] = []
        for item in provider_files:
            status = item.get("status")
            if isinstance(status, str) and status:
                file_statuses.append(status)

        normalized: list[str] = [self._normalize_status(s) for s in file_statuses]

        if any(s == "failed" for s in normalized):
            return "failed"
        if any(s == "in_progress" for s in normalized):
            return "in_progress"
        if provider_files and all(s == "completed" for s in normalized):
            return "completed"

        if isinstance(vector_store_payload, dict):
            status = vector_store_payload.get("status")
            if isinstance(status, str) and status:
                normalized_vs = self._normalize_status(status)
                if normalized_vs == "completed":
                    return "completed"
                return normalized_vs

        return "not_indexed"

    def _normalize_status(self, status: str) -> str:
        low = status.strip().lower()

        if low in {"failed", "error", "cancelled", "canceled"}:
            return "failed"
        if low in {"in_progress", "processing", "running", "queued"}:
            return "in_progress"
        if low in {"completed", "done", "success"}:
            return "completed"

        return low or "unknown"
