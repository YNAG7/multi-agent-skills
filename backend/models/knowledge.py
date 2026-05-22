from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    path: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
        index=True,
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        default="data",
        nullable=False,
        index=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    mtime: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_position"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_parent_chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chunk_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )

    vector_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )


class KnowledgeParentChunk(Base):
    __tablename__ = "knowledge_parent_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "parent_index", name="uq_knowledge_parent_position"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    parent_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    parent_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
