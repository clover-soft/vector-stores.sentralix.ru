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


class IndexFilesListOut(BaseModel):
    items: list[IndexFileOut]


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
