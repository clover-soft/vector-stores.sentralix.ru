from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagIndexFile(Base):
    __tablename__ = "rag_index_files"

    index_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    file_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    include_order: Mapped[int] = mapped_column(Integer)
