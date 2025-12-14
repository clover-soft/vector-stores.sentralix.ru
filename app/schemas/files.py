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

    external_file_id: str | None = None
    external_uploaded_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class FilesListOut(BaseModel):
    items: list[FileOut]


class FilePatchIn(BaseModel):
    file_name: str | None = Field(default=None)
    tags: dict | list | None = Field(default=None)
    notes: str | None = Field(default=None)
