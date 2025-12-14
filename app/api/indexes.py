from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.indexes import (
    IndexCreateIn,
    IndexFilesListOut,
    IndexFileOut,
    IndexesListOut,
    IndexOut,
    IndexPatchIn,
)
from schemas.files import FileOut
from services.index_files_service import IndexFilesService
from services.indexes_service import IndexesService

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
        chunking_strategy=payload.chunking_strategy,
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
        chunking_strategy=payload.chunking_strategy,
        expires_after=payload.expires_after,
        file_ids=payload.file_ids,
        metadata=payload.metadata,
    )
    if rag_index is None:
        raise HTTPException(status_code=404, detail="Индекс не найден")
    return IndexOut.model_validate(rag_index, from_attributes=True)


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
