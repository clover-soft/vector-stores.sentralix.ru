from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.files import FileOut


class IndexOut(BaseModel):
    id: str
    domain_id: str

    provider_type: str
    external_id: str | None = None

    index_type: str
    max_chunk_size: int | None = None
    chunk_overlap: int | None = None

    indexing_status: str
    indexed_at: datetime | None = None

    provider_ttl_days: int | None = None
    description: str | None = None

    created_at: datetime
    updated_at: datetime


class IndexCreateIn(BaseModel):
    provider_type: str
    index_type: str

    max_chunk_size: int | None = Field(default=None)
    chunk_overlap: int | None = Field(default=None)

    provider_ttl_days: int | None = Field(default=None)
    description: str | None = Field(default=None)


class IndexPatchIn(BaseModel):
    provider_type: str | None = Field(default=None)
    index_type: str | None = Field(default=None)

    max_chunk_size: int | None = Field(default=None)
    chunk_overlap: int | None = Field(default=None)

    provider_ttl_days: int | None = Field(default=None)
    description: str | None = Field(default=None)


class IndexesListOut(BaseModel):
    items: list[IndexOut]


class IndexFileOut(BaseModel):
    include_order: int
    file: FileOut


class IndexFilesListOut(BaseModel):
    items: list[IndexFileOut]
