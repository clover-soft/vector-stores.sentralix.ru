from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import get_config
from database import get_db
from schemas.admin_providers import (
    ProviderConnectionCreateIn,
    ProviderConnectionOut,
    ProviderConnectionPatchIn,
    ProviderConnectionsListOut,
    ProviderCredentialsEncryptIn,
    ProviderCredentialsEncryptOut,
    ProviderFileUploadCreateIn,
    ProviderFileUploadOut,
    ProviderFileUploadPatchIn,
    ProviderFileUploadsListOut,
    ProviderHealthOut,
    VectorStoreCreateIn,
    VectorStoreFileAttachIn,
    VectorStoreFileBatchCreateIn,
    VectorStoreFileUpdateIn,
    VectorStoreSearchIn,
    VectorStoreUpdateIn,
)
from services.provider_file_uploads_service import ProviderFileUploadsService
from services.provider_vector_stores_service import ProviderVectorStoresService
from services.providers_connections_service import ProvidersConnectionsService
from utils.crypto import encrypt_json

router = APIRouter(prefix="/api/v1/admin/providers", tags=["providers-admin"])


def _raise_provider_error(e: Exception) -> None:
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e)) from e
    if isinstance(e, NotImplementedError):
        raise HTTPException(status_code=501, detail=str(e)) from e
    raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/credentials/encrypt", response_model=ProviderCredentialsEncryptOut)
def encrypt_provider_credentials(payload: ProviderCredentialsEncryptIn):
    config = get_config()
    if not config.provider_secrets_key:
        raise HTTPException(status_code=500, detail="PROVIDER_SECRETS_KEY не задан")

    credentials_enc = encrypt_json(payload.credentials, config.provider_secrets_key)
    return ProviderCredentialsEncryptOut(credentials_enc=credentials_enc)


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
    except Exception as e:
        _raise_provider_error(e)


@router.post("/{provider_type}/vector-stores")
def create_vector_store(
    provider_type: str,
    payload: VectorStoreCreateIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.create_vector_store(provider_type=provider_type, **payload.model_dump())
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}")
def retrieve_vector_store(provider_type: str, vector_store_id: str, db: Session = Depends(get_db)):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.retrieve_vector_store(provider_type=provider_type, vector_store_id=vector_store_id)
    except Exception as e:
        _raise_provider_error(e)


@router.patch("/{provider_type}/vector-stores/{vector_store_id}")
def update_vector_store(
    provider_type: str,
    vector_store_id: str,
    payload: VectorStoreUpdateIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.update_vector_store(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            **payload.model_dump(),
        )
    except Exception as e:
        _raise_provider_error(e)


@router.delete("/{provider_type}/vector-stores/{vector_store_id}")
def delete_vector_store(provider_type: str, vector_store_id: str, db: Session = Depends(get_db)):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.delete_vector_store(provider_type=provider_type, vector_store_id=vector_store_id)
    except Exception as e:
        _raise_provider_error(e)


@router.post("/{provider_type}/vector-stores/{vector_store_id}/search")
def search_vector_store(
    provider_type: str,
    vector_store_id: str,
    payload: VectorStoreSearchIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        items = service.search_vector_store(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            **payload.model_dump(),
        )
        return {"items": items}
    except Exception as e:
        _raise_provider_error(e)


@router.post("/{provider_type}/vector-stores/{vector_store_id}/files")
def attach_file_to_vector_store(
    provider_type: str,
    vector_store_id: str,
    payload: VectorStoreFileAttachIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.attach_file_to_vector_store(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            **payload.model_dump(),
        )
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}/files")
def list_vector_store_files(
    provider_type: str,
    vector_store_id: str,
    limit: int = 100,
    after: str | None = None,
    before: str | None = None,
    order: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        items = service.list_vector_store_files(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            limit=limit,
            after=after,
            before=before,
            order=order,
            status_filter=status_filter,
        )
        return {"items": items}
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}/files/{file_id}")
def retrieve_vector_store_file(
    provider_type: str,
    vector_store_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.retrieve_vector_store_file(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
    except Exception as e:
        _raise_provider_error(e)


@router.patch("/{provider_type}/vector-stores/{vector_store_id}/files/{file_id}")
def update_vector_store_file(
    provider_type: str,
    vector_store_id: str,
    file_id: str,
    payload: VectorStoreFileUpdateIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.update_vector_store_file(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            file_id=file_id,
            **payload.model_dump(),
        )
    except Exception as e:
        _raise_provider_error(e)


@router.delete("/{provider_type}/vector-stores/{vector_store_id}/files/{file_id}")
def detach_file_from_vector_store(
    provider_type: str,
    vector_store_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.detach_file_from_vector_store(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}/files/{file_id}/content")
def retrieve_vector_store_file_content(
    provider_type: str,
    vector_store_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        items = service.retrieve_vector_store_file_content(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        return {"items": items}
    except Exception as e:
        _raise_provider_error(e)


@router.post("/{provider_type}/vector-stores/{vector_store_id}/file-batches")
def create_vector_store_file_batch(
    provider_type: str,
    vector_store_id: str,
    payload: VectorStoreFileBatchCreateIn,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.create_vector_store_file_batch(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            **payload.model_dump(),
        )
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}/file-batches/{batch_id}")
def retrieve_vector_store_file_batch(
    provider_type: str,
    vector_store_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.retrieve_vector_store_file_batch(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            batch_id=batch_id,
        )
    except Exception as e:
        _raise_provider_error(e)


@router.post("/{provider_type}/vector-stores/{vector_store_id}/file-batches/{batch_id}/cancel")
def cancel_vector_store_file_batch(
    provider_type: str,
    vector_store_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        return service.cancel_vector_store_file_batch(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            batch_id=batch_id,
        )
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/vector-stores/{vector_store_id}/file-batches/{batch_id}/files")
def list_vector_store_file_batch_files(
    provider_type: str,
    vector_store_id: str,
    batch_id: str,
    limit: int = 100,
    after: str | None = None,
    before: str | None = None,
    order: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        service = ProviderVectorStoresService(db=db)
        items = service.list_vector_store_file_batch_files(
            provider_type=provider_type,
            vector_store_id=vector_store_id,
            batch_id=batch_id,
            limit=limit,
            after=after,
            before=before,
            order=order,
            status_filter=status_filter,
        )
        return {"items": items}
    except Exception as e:
        _raise_provider_error(e)


@router.get("/{provider_type}/files")
def list_files(provider_type: str, limit: int = 100, db: Session = Depends(get_db)):
    try:
        service = ProviderVectorStoresService(db=db)
        return {"items": service.list_files(provider_type=provider_type, limit=limit)}
    except Exception as e:
        _raise_provider_error(e)


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
