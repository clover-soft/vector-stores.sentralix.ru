from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FileOut(BaseModel):
    id: str
    domain_id: str

    file_name: str
    file_type: str
    local_path: str
    size_bytes: int

    tags: dict | list | None = None
    notes: str | None = None

    chunking_strategy: dict | None = None

    created_at: datetime
    updated_at: datetime


class FilesListOut(BaseModel):
    items: list[FileOut]


class FilePatchIn(BaseModel):
    file_name: str | None = Field(default=None)
    tags: dict | list | None = Field(default=None)
    notes: str | None = Field(default=None)
    chunking_strategy: dict | None = Field(default=None)


class FileChangeDomainIn(BaseModel):
    new_domain_id: str


class FileChangeDomainOut(BaseModel):
    file: FileOut
    old_domain_id: str
    new_domain_id: str
    moved_on_disk: bool
    detached_index_links: int
    indexes_file_ids_updated: int
