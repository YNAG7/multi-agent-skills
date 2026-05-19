# backend/services/chat_service.py

import asyncio
import json

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.repositories.chat_repository import (
    delete_session,
    ensure_session,
    list_messages,
    list_sessions,
    save_message,
)
from backend.schemas.chat import ChatRequest
from backend.schemas.user import CurrentUser
from backend.services.agent_service import agent_service
from backend.services.context_service import build_agent_context, compress_thread_if_needed
from backend.services.mem0_service import mem0_service
from utils.logger_handler import logger


async def finalize_chat_turn(
    user_id: int,
    thread_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    db = SessionLocal()

    try:
        await compress_thread_if_needed(
            db=db,
            user_id=user_id,
            thread_id=thread_id,
        )

        mem0_service.add_turn(
            user_id=user_id,
            thread_id=thread_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
    except Exception as e:
        logger.warning(f"[Chat] postprocess failed: {e}")
    finally:
        db.close()


async def chat_with_agent(
    db: Session,
    req: ChatRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    safe_thread_id = f"user_{current_user.id}:{req.thread_id}"

    ensure_session(
        db=db,
        user_id=current_user.id,
        thread_id=req.thread_id,
        title=req.message[:30],
    )

    save_message(
        db=db,
        user_id=current_user.id,
        thread_id=req.thread_id,
        role="user",
        content=req.message,
    )


    full_assistant_message = ""
    context_text = build_agent_context(
        db=db,
        user_id=current_user.id,
        thread_id=req.thread_id,
        current_message=req.message,
    )

    async for chunk_text in agent_service.stream_chat(
        message=req.message,
        thread_id=safe_thread_id,
        context_text=context_text,
    ):
        if chunk_text:

            full_assistant_message += chunk_text
            
            yield f"data: {json.dumps({'content': chunk_text}, ensure_ascii=False)}\n\n"

    save_message(
        db=db,
        user_id=current_user.id,
        thread_id=req.thread_id,
        role="assistant",
        content=full_assistant_message
    )

    if background_tasks is not None:
        background_tasks.add_task(
            finalize_chat_turn,
            current_user.id,
            req.thread_id,
            req.message,
            full_assistant_message,
        )
    else:
        asyncio.create_task(
            finalize_chat_turn(
                user_id=current_user.id,
                thread_id=req.thread_id,
                user_message=req.message,
                assistant_message=full_assistant_message,
            )
        )
    
    yield "data: [DONE]\n\n"

    


def get_user_sessions(db: Session, user_id: int) -> list[dict]:
    sessions = list_sessions(db, user_id)

    return [
        {
            "thread_id": item.thread_id,
            "title": item.title,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in sessions
    ]


def get_user_messages(
    db: Session,
    user_id: int,
    thread_id: str,
) -> list[dict]:
    messages = list_messages(
        db=db,
        user_id=user_id,
        thread_id=thread_id,
    )

    return [
        {
            "role": item.role,
            "content": item.content,
            "created_at": item.created_at.isoformat(),
        }
        for item in messages
    ]


def delete_user_session(
    db: Session,
    user_id: int,
    thread_id: str,
) -> bool:
    return delete_session(db=db, user_id=user_id, thread_id=thread_id)
