from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.providers import ProviderHealthOut, ProviderPublicOut, ProvidersPublicListOut
from services.providers_connections_service import ProvidersConnectionsService

router = APIRouter(prefix="/api/v1", tags=["providers"])


@router.get("/providers", response_model=ProvidersPublicListOut)
def list_providers(db: Session = Depends(get_db)):
    service = ProvidersConnectionsService(db=db)
    items = service.list_connections()

    out: list[ProviderPublicOut] = []
    for c in items:
        out.append(ProviderPublicOut(provider_type=c.id, is_enabled=bool(c.is_enabled)))

    return ProvidersPublicListOut(items=out)


@router.get("/providers/{provider_type}/health", response_model=ProviderHealthOut)
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
