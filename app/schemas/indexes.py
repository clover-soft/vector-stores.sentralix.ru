from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.files import FileOut


class IndexOut(BaseModel):
    id: str
    domain_id: str

    provider_type: str
    external_id: str | None = None

    name: str | None = None
    description: str | None = None

    expires_after: dict | None = None
    file_ids: list[str] | None = None
    metadata: dict | None = Field(default=None, validation_alias="metadata_")

    indexing_status: str
    indexed_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class IndexCreateIn(BaseModel):
    provider_type: str

    name: str | None = Field(default=None)
    description: str | None = Field(default=None)

    expires_after: dict | None = Field(default=None)
    file_ids: list[str] | None = Field(default=None)
    metadata: dict | None = Field(default=None)


class IndexPatchIn(BaseModel):
    provider_type: str | None = Field(default=None)

    name: str | None = Field(default=None)
    description: str | None = Field(default=None)

    expires_after: dict | None = Field(default=None)
    file_ids: list[str] | None = Field(default=None)
    metadata: dict | None = Field(default=None)


class IndexesListOut(BaseModel):
    items: list[IndexOut]


class IndexFileOut(BaseModel):
    include_order: int
    file: FileOut
    external_id: str | None = None
    chunking_strategy: dict | None = None


class IndexFilesListOut(BaseModel):
    items: list[IndexFileOut]


class AttachFileIn(BaseModel):
    chunking_strategy: dict | None = None


class IndexProviderUploadOut(BaseModel):
    status: str
    last_error: str | None = None
    external_file_id: str | None = None


class IndexProviderFileOut(BaseModel):
    include_order: int
    file: FileOut
    provider_upload: IndexProviderUploadOut | None = None
    provider_vector_store_file: dict | None = None


class IndexProviderFilesOut(BaseModel):
    provider_type: str
    vector_store_id: str | None = None
    items: list[IndexProviderFileOut]
    errors: list[str]


class IndexSearchIn(BaseModel):
    query: str | list[str]
    filters: dict | None = None
    max_num_results: int | None = None
    ranking_options: dict | None = None
    rewrite_query: bool | None = None


class IndexSearchOut(BaseModel):
    items: list[dict]


class IndexSyncReportOut(BaseModel):
    provider_type: str
    vector_store_id: str
    provider_files_count: int
    aggregated_status: str
    forced: bool
    skipped: bool


class IndexSyncOut(BaseModel):
    item: IndexOut
    sync_report: IndexSyncReportOut


class IndexesSyncOut(BaseModel):
    items: list[IndexOut]
    errors: list[str]


class IndexPublishOut(BaseModel):
    provider_type: str
    vector_store_id: str | None = None

    dry_run: bool
    created_vector_store: bool
    will_create_vector_store: bool

    desired_provider_file_ids: list[str]
    existing_provider_file_ids: list[str]
    missing_provider_file_ids: list[str]
    extra_provider_file_ids: list[str]
    missing_upload_local_file_ids: list[str]

    attached_count: int
    detached_count: int

    attach_results: list[dict]
    errors: list[str]
