from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.indexes import (
    IndexCreateIn,
    IndexFilesListOut,
    IndexFileOut,
    IndexesListOut,
    IndexesSyncOut,
    IndexOut,
    IndexPatchIn,
    IndexSyncOut,
)
from schemas.files import FileOut
from services.index_files_service import IndexFilesService
from services.indexes_service import IndexesService
from services.index_publish_service import IndexPublishService
from services.indexes_sync_service import IndexesSyncService

router = APIRouter(prefix="/api/v1", tags=["indexes"])


def get_domain_id(x_domain_id: str | None = Header(default=None, alias="X-Domain-Id")) -> str:
    if not x_domain_id or not x_domain_id.strip():
        raise HTTPException(status_code=400, detail="X-Domain-Id обязателен")
    return x_domain_id.strip()


@router.post("/indexes", response_model=IndexOut)
def create_index(
    payload: IndexCreateIn,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesService(db=db, domain_id=domain_id)
    rag_index = service.create_index(
        provider_type=payload.provider_type,
        name=payload.name,
        description=payload.description,
        expires_after=payload.expires_after,
        file_ids=payload.file_ids,
        metadata=payload.metadata,
    )
    return IndexOut.model_validate(rag_index, from_attributes=True)


@router.get("/indexes", response_model=IndexesListOut)
def list_indexes(
    skip: int = 0,
    limit: int = 100,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesService(db=db, domain_id=domain_id)
    items = service.list_indexes(skip=skip, limit=limit)
    return IndexesListOut(items=[IndexOut.model_validate(i, from_attributes=True) for i in items])


@router.get("/indexes/{index_id}", response_model=IndexOut)
def get_index(
    index_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesService(db=db, domain_id=domain_id)
    rag_index = service.get_index(index_id)
    if rag_index is None:
        raise HTTPException(status_code=404, detail="Индекс не найден")
    return IndexOut.model_validate(rag_index, from_attributes=True)


@router.patch("/indexes/{index_id}", response_model=IndexOut)
def patch_index(
    index_id: str,
    payload: IndexPatchIn,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesService(db=db, domain_id=domain_id)
    rag_index = service.update_index(
        index_id=index_id,
        provider_type=payload.provider_type,
        name=payload.name,
        description=payload.description,
        expires_after=payload.expires_after,
        file_ids=payload.file_ids,
        metadata=payload.metadata,
    )
    if rag_index is None:
        raise HTTPException(status_code=404, detail="Индекс не найден")
    return IndexOut.model_validate(rag_index, from_attributes=True)


@router.post("/indexes/{index_id}/publish")
def publish_index(
    index_id: str,
    detach_extra: bool = True,
    force_upload: bool = False,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexPublishService(db=db, domain_id=domain_id)
    try:
        result = service.publish(index_id=index_id, force_upload=force_upload, detach_extra=detach_extra)
    except ValueError as e:
        detail = str(e)
        if detail == "Индекс не найден":
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка публикации в провайдер: {e}") from e

    return {
        "provider_type": result.get("provider_type"),
        "vector_store_id": result.get("vector_store_id"),
        "created_vector_store": bool(result.get("created_vector_store")),
        "attached_count": int(result.get("attached_count") or 0),
        "detached_count": int(result.get("detached_count") or 0),
        "attach_results": result.get("attach_results") or [],
        "errors": result.get("errors") or [],
    }


@router.post("/indexes/{index_id}/sync", response_model=IndexSyncOut)
def sync_index(
    index_id: str,
    force: bool = False,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesSyncService(db=db, domain_id=domain_id)
    try:
        result = service.sync_index(index_id=index_id, force=force)
    except ValueError as e:
        detail = str(e)
        if detail == "Индекс не найден":
            raise HTTPException(status_code=404, detail=detail) from e
        if detail == "У индекса нет external_id":
            raise HTTPException(status_code=409, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка синхронизации с провайдером: {e}") from e

    rag_index = result.get("rag_index")
    return IndexSyncOut(
        item=IndexOut.model_validate(rag_index, from_attributes=True),
        sync_report=result.get("sync_report") or {},
    )


@router.post("/indexes/sync", response_model=IndexesSyncOut)
def sync_indexes(
    provider_type: str | None = None,
    force: bool = False,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesSyncService(db=db, domain_id=domain_id)
    try:
        result = service.sync_domain_indexes(provider_type=provider_type, force=force)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка синхронизации с провайдером: {e}") from e

    items = result.get("items") or []
    errors = result.get("errors") or []

    return IndexesSyncOut(
        items=[IndexOut.model_validate(i, from_attributes=True) for i in items],
        errors=errors,
    )


@router.delete("/indexes/{index_id}")
def delete_index(
    index_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexesService(db=db, domain_id=domain_id)
    ok = service.delete_index(index_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Индекс не найден")
    return {"status": "ok"}


@router.post("/indexes/{index_id}/files/{file_id}")
def attach_file(
    index_id: str,
    file_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexFilesService(db=db, domain_id=domain_id)
    try:
        service.attach_file(index_id=index_id, file_id=file_id)
    except ValueError as e:
        detail = str(e)
        if detail == "Файл уже привязан к индексу":
            raise HTTPException(status_code=409, detail=detail) from e
        raise HTTPException(status_code=404, detail=detail) from e

    return {"status": "ok"}


@router.delete("/indexes/{index_id}/files/{file_id}")
def detach_file(
    index_id: str,
    file_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexFilesService(db=db, domain_id=domain_id)
    ok = service.detach_file(index_id=index_id, file_id=file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Связь индекс↔файл не найдена")
    return {"status": "ok"}


@router.get("/indexes/{index_id}/files", response_model=IndexFilesListOut)
def list_index_files(
    index_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = IndexFilesService(db=db, domain_id=domain_id)
    rows = service.list_files(index_id=index_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="Индекс не найден")

    items: list[IndexFileOut] = []
    for include_order, rag_file in rows:
        items.append(
            IndexFileOut(
                include_order=include_order,
                file=FileOut.model_validate(rag_file, from_attributes=True),
            )
        )

    return IndexFilesListOut(items=items)
