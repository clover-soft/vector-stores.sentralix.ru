from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RagIndexFile(Base):
    __tablename__ = "rag_index_files"

    index_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_indexes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_files.id", ondelete="CASCADE"),
        primary_key=True,
    )
    include_order: Mapped[int] = mapped_column(Integer)
