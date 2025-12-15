from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagProviderConnection(Base):
    __tablename__ = "rag_provider_connections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    auth_type: Mapped[str] = mapped_column(String(32))

    credentials_enc: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_enc: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_healthcheck_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
