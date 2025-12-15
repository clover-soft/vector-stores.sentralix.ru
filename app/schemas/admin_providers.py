from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderConnectionOut(BaseModel):
    provider_type: str

    base_url: str | None = None
    auth_type: str

    is_enabled: bool
    last_healthcheck_at: datetime | None = None
    last_error: str | None = None

    has_credentials: bool
    has_token: bool
    token_expires_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class ProviderConnectionCreateIn(BaseModel):
    base_url: str | None = None
    auth_type: str

    credentials: dict | None = None
    token: dict | None = None
    token_expires_at: datetime | None = None

    is_enabled: bool = True


class ProviderConnectionPatchIn(BaseModel):
    base_url: str | None = None
    auth_type: str | None = None

    credentials: dict | None = None
    token: dict | None = None
    token_expires_at: datetime | None = None

    is_enabled: bool | None = None


class ProviderConnectionsListOut(BaseModel):
    items: list[ProviderConnectionOut]


class ProviderHealthOut(BaseModel):
    provider_type: str
    status: str
    detail: str | None = None


class ProviderFileUploadOut(BaseModel):
    id: str
    provider_id: str
    local_file_id: str

    external_file_id: str | None = None
    external_uploaded_at: datetime | None = None

    content_sha256: str
    status: str
    last_error: str | None = None

    raw_provider_json: dict | None = None

    created_at: datetime
    updated_at: datetime


class ProviderFileUploadCreateIn(BaseModel):
    local_file_id: str
    force: bool = False
    meta: dict | None = None


class ProviderFileUploadPatchIn(BaseModel):
    status: str | None = None
    last_error: str | None = None


class ProviderFileUploadsListOut(BaseModel):
    items: list[ProviderFileUploadOut]


class VectorStoreCreateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    chunking_strategy: dict | None = None
    expires_after: dict | None = None
    file_ids: list[str] | None = None
    metadata: dict[str, str] | None = None


class VectorStoreUpdateIn(BaseModel):
    name: str | None = None
    expires_after: dict | None = None
    metadata: dict[str, str] | None = None


class VectorStoreSearchIn(BaseModel):
    query: str | list[str]
    filters: dict | None = None
    max_num_results: int | None = None
    ranking_options: dict | None = None
    rewrite_query: bool | None = None


class VectorStoreFileAttachIn(BaseModel):
    file_id: str
    attributes: dict | None = None
    chunking_strategy: dict | None = None


class VectorStoreFileUpdateIn(BaseModel):
    attributes: dict


class VectorStoreFileBatchCreateIn(BaseModel):
    file_ids: list[str] | None = None
    files: list[dict] | None = None
    attributes: dict | None = None
    chunking_strategy: dict | None = None
