# backend/api/chat_api.py

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from backend.db.database import get_db
from backend.deps import get_current_user
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.schemas.user import CurrentUser
from backend.services.chat_service import (
    delete_user_session,
    chat_with_agent,
    get_user_messages,
    get_user_sessions,
)


router = APIRouter()


@router.post("")
async def chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    generator = chat_with_agent(
        db=db,
        req=req,
        current_user=current_user,
        background_tasks=background_tasks,
    )

    return StreamingResponse(generator, media_type="text/event-stream")


@router.get("/sessions")
def sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "sessions": get_user_sessions(db, current_user.id)
    }


@router.get("/sessions/{thread_id}/messages")
def messages(
    thread_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "messages": get_user_messages(
            db=db,
            user_id=current_user.id,
            thread_id=thread_id,
        )
    }


@router.delete("/sessions/{thread_id}")
def delete_session(
    thread_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = delete_user_session(
        db=db,
        user_id=current_user.id,
        thread_id=thread_id,
    )

    return {
        "deleted": deleted
    }
