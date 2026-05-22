from __future__ import annotations

from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.models import KnowledgeDocument
from rag.vector_store import VectorStoreService


_vector_service: VectorStoreService | None = None


def vector_service() -> VectorStoreService:
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
    return _vector_service


def _document_payload(document: KnowledgeDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "path": document.path,
        "filename": document.filename,
        "source": document.source,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "mtime": document.mtime,
        "content_hash": document.content_hash,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error": document.error,
        "uploaded_by": document.uploaded_by,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
    }


def refresh_runtime_rag() -> None:
    try:
        from agent.tools.common_tools import get_initialized_rag

        rag = get_initialized_rag()
        if rag is not None:
            rag.refresh_retrievers(reload_vector_store=True)
    except Exception:
        return


def list_knowledge_documents(db: Session) -> list[dict[str, Any]]:
    return [
        _document_payload(document)
        for document in vector_service().list_documents(db)
    ]


async def upload_knowledge_file(
    db: Session,
    file: UploadFile,
    uploaded_by: int | None = None,
) -> dict[str, Any]:
    document = await vector_service().save_upload(db, file, uploaded_by=uploaded_by)
    refresh_runtime_rag()
    return _document_payload(document)


def sync_knowledge_directory() -> dict[str, int]:
    stats = vector_service().sync_data_directory()
    refresh_runtime_rag()
    return stats


def reindex_knowledge_document(db: Session, document_id: int) -> dict[str, Any]:
    document = vector_service().reindex_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")

    refresh_runtime_rag()
    return _document_payload(document)


def delete_knowledge_document(
    db: Session,
    document_id: int,
    remove_file: bool = True,
) -> None:
    deleted = vector_service().delete_document(
        db,
        document_id=document_id,
        remove_file=remove_file,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge document not found")

    refresh_runtime_rag()
