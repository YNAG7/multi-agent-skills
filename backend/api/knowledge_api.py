from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.deps import require_admin
from backend.schemas.user import CurrentUser
from backend.services import knowledge_service
from backend.services.ragas_eval_service import evaluate_jsonl


router = APIRouter()


class KnowledgeEvalRequest(BaseModel):
    jsonl: str = Field(min_length=1)
    sync: bool = False


@router.get("")
def list_documents(
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "documents": knowledge_service.list_knowledge_documents(db)
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "document": await knowledge_service.upload_knowledge_file(
            db,
            file,
            uploaded_by=current_user.id,
        )
    }


@router.post("/sync")
def sync_documents(
    current_user: CurrentUser = Depends(require_admin),
):
    return {
        "stats": knowledge_service.sync_knowledge_directory()
    }


@router.post("/evaluate")
def evaluate_knowledge(
    req: KnowledgeEvalRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    return evaluate_jsonl(req.jsonl, sync=req.sync)


@router.post("/{document_id}/reindex")
def reindex_document(
    document_id: int,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "document": knowledge_service.reindex_knowledge_document(db, document_id)
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    knowledge_service.delete_knowledge_document(db, document_id, remove_file=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
