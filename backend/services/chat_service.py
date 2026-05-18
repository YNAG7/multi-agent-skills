# backend/services/chat_service.py

from sqlalchemy.orm import Session

from backend.repositories.chat_repository import (
    ensure_session,
    list_messages,
    list_sessions,
    save_message,
)
from backend.schemas.chat import ChatRequest
from backend.schemas.user import CurrentUser
from backend.services.agent_service import agent_service


async def chat_with_agent(
    db: Session,
    req: ChatRequest,
    current_user: CurrentUser,
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

    # 1. 准备一个空字符串，用于把流式返回的文字碎片拼接起来，以便最后存入数据库
    full_assistant_message = ""

    # 2. 这里的 agent_service.chat 需要被替换为支持流式的函数 (例如叫 stream_chat)
    # 它必须是一个返回字词碎片的异步生成器
    async for chunk_text in agent_service.stream_chat(
        message=req.message,
        thread_id=safe_thread_id,
    ):
        if chunk_text:
            # 拼接完整的回复内容
            full_assistant_message += chunk_text
            
            yield f"data: {chunk_text}\n\n"

    save_message(
        db=db,
        user_id=current_user.id,
        thread_id=req.thread_id,
        role="assistant",
        content=full_assistant_message
    )

    


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