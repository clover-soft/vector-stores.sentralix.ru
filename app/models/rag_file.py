from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagFile(Base):
    __tablename__ = "rag_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain_id: Mapped[str] = mapped_column(String(128), index=True)

    file_name: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(128))
    local_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger)

    external_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tags: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
