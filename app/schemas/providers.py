from __future__ import annotations

from pydantic import BaseModel


class ProviderPublicOut(BaseModel):
    provider_type: str
    is_enabled: bool


class ProvidersPublicListOut(BaseModel):
    items: list[ProviderPublicOut]


class ProviderHealthOut(BaseModel):
    provider_type: str
    status: str
    detail: str | None = None
