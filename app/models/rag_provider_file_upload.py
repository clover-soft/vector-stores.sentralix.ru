from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagProviderFileUpload(Base):
    __tablename__ = "rag_provider_file_uploads"
    __table_args__ = (
        UniqueConstraint("provider_id", "local_file_id", name="uq_rag_provider_file_uploads_provider_file"),
        UniqueConstraint(
            "provider_id",
            "external_file_id",
            name="uq_rag_provider_file_uploads_provider_external_file",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    provider_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    local_file_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )

    external_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    content_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_provider_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
