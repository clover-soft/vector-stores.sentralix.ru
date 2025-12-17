from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagIndex(Base):
    __tablename__ = "rag_indexes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain_id: Mapped[str] = mapped_column(String(128), index=True)

    provider_type: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    expires_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    indexing_status: Mapped[str] = mapped_column(String(32), default="not_indexed")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
