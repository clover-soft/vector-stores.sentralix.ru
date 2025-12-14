from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from schemas.files import FileOut, FilePatchIn, FilesListOut
from services.files_service import FilesService, parse_chunking_strategy, parse_tags

router = APIRouter(prefix="/api/v1", tags=["files"])


def get_domain_id(x_domain_id: str | None = Header(default=None, alias="X-Domain-Id")) -> str:
    if not x_domain_id or not x_domain_id.strip():
        raise HTTPException(status_code=400, detail="X-Domain-Id обязателен")
    return x_domain_id.strip()


@router.post("/files", response_model=FileOut)
def upload_file(
    file: UploadFile = File(...),
    file_type: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    chunking_strategy: str | None = Form(default=None),
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    try:
        parsed_tags = parse_tags(tags)
        parsed_chunking_strategy = parse_chunking_strategy(chunking_strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    service = FilesService(db=db, domain_id=domain_id)
    rag_file = service.create_file(
        upload=file,
        file_type=file_type,
        tags=parsed_tags,
        notes=notes,
        chunking_strategy=parsed_chunking_strategy,
    )
    return FileOut.model_validate(rag_file, from_attributes=True)


@router.get("/files", response_model=FilesListOut)
def list_files(
    skip: int = 0,
    limit: int = 100,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = FilesService(db=db, domain_id=domain_id)
    items = service.list_files(skip=skip, limit=limit)
    return FilesListOut(items=[FileOut.model_validate(i, from_attributes=True) for i in items])


@router.get("/files/{file_id}", response_model=FileOut)
def get_file(
    file_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = FilesService(db=db, domain_id=domain_id)
    rag_file = service.get_file(file_id)
    if rag_file is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileOut.model_validate(rag_file, from_attributes=True)


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = FilesService(db=db, domain_id=domain_id)
    rag_file = service.get_file(file_id)
    if rag_file is None:
        raise HTTPException(status_code=404, detail="Файл не найден")

    if not Path(rag_file.local_path).exists():
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=rag_file.local_path,
        filename=rag_file.file_name,
        media_type=rag_file.file_type,
    )


@router.patch("/files/{file_id}", response_model=FileOut)
def patch_file(
    file_id: str,
    payload: FilePatchIn,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = FilesService(db=db, domain_id=domain_id)
    try:
        rag_file = service.update_file(
            file_id=file_id,
            file_name=payload.file_name,
            tags=payload.tags,
            notes=payload.notes,
            chunking_strategy=payload.chunking_strategy,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if rag_file is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileOut.model_validate(rag_file, from_attributes=True)


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    domain_id: str = Depends(get_domain_id),
    db: Session = Depends(get_db),
):
    service = FilesService(db=db, domain_id=domain_id)
    ok = service.delete_file(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return {"status": "ok"}
