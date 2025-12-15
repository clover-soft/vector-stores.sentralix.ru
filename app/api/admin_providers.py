from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.admin_providers import (
    ProviderConnectionCreateIn,
    ProviderConnectionOut,
    ProviderConnectionPatchIn,
    ProviderConnectionsListOut,
    ProviderFileUploadCreateIn,
    ProviderFileUploadOut,
    ProviderFileUploadPatchIn,
    ProviderFileUploadsListOut,
    ProviderHealthOut,
)
from services.provider_file_uploads_service import ProviderFileUploadsService
from services.provider_vector_stores_service import ProviderVectorStoresService
from services.providers_connections_service import ProvidersConnectionsService

router = APIRouter(prefix="/api/v1/admin/providers", tags=["providers-admin"])


@router.get("/connections", response_model=ProviderConnectionsListOut)
def list_connections(db: Session = Depends(get_db)):
    service = ProvidersConnectionsService(db=db)
    items = service.list_connections()

    out: list[ProviderConnectionOut] = []
    for c in items:
        out.append(
            ProviderConnectionOut(
                provider_type=c.id,
                base_url=c.base_url,
                auth_type=c.auth_type,
                is_enabled=c.is_enabled,
                last_healthcheck_at=c.last_healthcheck_at,
                last_error=c.last_error,
                has_credentials=bool(c.credentials_enc),
                has_token=bool(c.token_enc),
                token_expires_at=c.token_expires_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return ProviderConnectionsListOut(items=out)


@router.get("/connections/{provider_type}", response_model=ProviderConnectionOut)
def get_connection(provider_type: str, db: Session = Depends(get_db)):
    service = ProvidersConnectionsService(db=db)
    c = service.get_connection(provider_type)
    if c is None:
        raise HTTPException(status_code=404, detail="Подключение провайдера не найдено")

    return ProviderConnectionOut(
        provider_type=c.id,
        base_url=c.base_url,
        auth_type=c.auth_type,
        is_enabled=c.is_enabled,
        last_healthcheck_at=c.last_healthcheck_at,
        last_error=c.last_error,
        has_credentials=bool(c.credentials_enc),
        has_token=bool(c.token_enc),
        token_expires_at=c.token_expires_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/connections/{provider_type}", response_model=ProviderConnectionOut)
def create_connection(
    provider_type: str,
    payload: ProviderConnectionCreateIn,
    db: Session = Depends(get_db),
):
    service = ProvidersConnectionsService(db=db)

    c = service.upsert_connection(
        provider_type=provider_type,
        base_url=payload.base_url,
        auth_type=payload.auth_type,
        credentials=payload.credentials,
        token=payload.token,
        token_expires_at=payload.token_expires_at,
        is_enabled=payload.is_enabled,
    )

    return ProviderConnectionOut(
        provider_type=c.id,
        base_url=c.base_url,
        auth_type=c.auth_type,
        is_enabled=c.is_enabled,
        last_healthcheck_at=c.last_healthcheck_at,
        last_error=c.last_error,
        has_credentials=bool(c.credentials_enc),
        has_token=bool(c.token_enc),
        token_expires_at=c.token_expires_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.patch("/connections/{provider_type}", response_model=ProviderConnectionOut)
def patch_connection(
    provider_type: str,
    payload: ProviderConnectionPatchIn,
    db: Session = Depends(get_db),
):
    service = ProvidersConnectionsService(db=db)

    c = service.patch_connection(
        provider_type=provider_type,
        base_url=payload.base_url,
        auth_type=payload.auth_type,
        credentials=payload.credentials,
        token=payload.token,
        token_expires_at=payload.token_expires_at,
        is_enabled=payload.is_enabled,
    )
    if c is None:
        raise HTTPException(status_code=404, detail="Подключение провайдера не найдено")

    return ProviderConnectionOut(
        provider_type=c.id,
        base_url=c.base_url,
        auth_type=c.auth_type,
        is_enabled=c.is_enabled,
        last_healthcheck_at=c.last_healthcheck_at,
        last_error=c.last_error,
        has_credentials=bool(c.credentials_enc),
        has_token=bool(c.token_enc),
        token_expires_at=c.token_expires_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.delete("/connections/{provider_type}")
def delete_connection(provider_type: str, db: Session = Depends(get_db)):
    service = ProvidersConnectionsService(db=db)
    ok = service.delete_connection(provider_type)
    if not ok:
        raise HTTPException(status_code=404, detail="Подключение провайдера не найдено")
    return {"status": "ok"}


@router.get("/{provider_type}/health", response_model=ProviderHealthOut)
def provider_health(provider_type: str, db: Session = Depends(get_db)):
    service = ProvidersConnectionsService(db=db)
    c = service.get_connection(provider_type)
    if c is None:
        raise HTTPException(status_code=404, detail="Подключение провайдера не найдено")

    try:
        provider = service.get_provider(provider_type)
        provider.healthcheck()
        c.last_healthcheck_at = datetime.utcnow()
        c.last_error = None
        db.commit()
        return ProviderHealthOut(provider_type=provider_type, status="ok")
    except Exception as e:
        c.last_healthcheck_at = datetime.utcnow()
        c.last_error = str(e)
        db.commit()
        return ProviderHealthOut(provider_type=provider_type, status="failed", detail=str(e))


@router.get("/{provider_type}/vector-stores")
def list_vector_stores(provider_type: str, limit: int = 100, db: Session = Depends(get_db)):
    try:
        service = ProviderVectorStoresService(db=db)
        return {"items": service.list_vector_stores(provider_type=provider_type, limit=limit)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{provider_type}/files")
def list_files(provider_type: str, limit: int = 100, db: Session = Depends(get_db)):
    try:
        service = ProviderVectorStoresService(db=db)
        return {"items": service.list_files(provider_type=provider_type, limit=limit)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{provider_type}/file-uploads", response_model=ProviderFileUploadsListOut)
def list_file_uploads(
    provider_type: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    service = ProviderFileUploadsService(db=db)
    items = service.list_uploads(provider_type=provider_type, skip=skip, limit=limit)
    return ProviderFileUploadsListOut(
        items=[ProviderFileUploadOut.model_validate(i, from_attributes=True) for i in items]
    )


@router.get("/{provider_type}/file-uploads/{upload_id}", response_model=ProviderFileUploadOut)
def get_file_upload(provider_type: str, upload_id: str, db: Session = Depends(get_db)):
    service = ProviderFileUploadsService(db=db)
    item = service.get_upload(provider_type=provider_type, upload_id=upload_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return ProviderFileUploadOut.model_validate(item, from_attributes=True)


@router.post("/{provider_type}/file-uploads", response_model=ProviderFileUploadOut)
def sync_file_upload(
    provider_type: str,
    payload: ProviderFileUploadCreateIn,
    db: Session = Depends(get_db),
):
    service = ProviderFileUploadsService(db=db)
    try:
        item = service.get_or_sync(
            provider_type=provider_type,
            local_file_id=payload.local_file_id,
            force=payload.force,
            meta=payload.meta,
        )
        return ProviderFileUploadOut.model_validate(item, from_attributes=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{provider_type}/file-uploads/{upload_id}", response_model=ProviderFileUploadOut)
def patch_file_upload(
    provider_type: str,
    upload_id: str,
    payload: ProviderFileUploadPatchIn,
    db: Session = Depends(get_db),
):
    service = ProviderFileUploadsService(db=db)
    item = service.patch_upload(
        provider_type=provider_type,
        upload_id=upload_id,
        status=payload.status,
        last_error=payload.last_error,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return ProviderFileUploadOut.model_validate(item, from_attributes=True)


@router.delete("/{provider_type}/file-uploads/{upload_id}")
def delete_file_upload(provider_type: str, upload_id: str, db: Session = Depends(get_db)):
    service = ProviderFileUploadsService(db=db)
    ok = service.delete_upload(provider_type=provider_type, upload_id=upload_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"status": "ok"}
