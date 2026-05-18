# backend/repositories/chat_repository.py

from datetime import datetime

from sqlalchemy.orm import Session

from backend.models import ChatSession, ChatMessage


def ensure_session(
    db: Session,
    user_id: int,
    thread_id: str,
    title: str | None = None,
) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.thread_id == thread_id,
        )
        .first()
    )

    if session:
        session.updated_at = datetime.now()

        if title and not session.title:
            session.title = title

    else:
        session = ChatSession(
            user_id=user_id,
            thread_id=thread_id,
            title=title or "新会话",
        )
        db.add(session)

    db.commit()
    db.refresh(session)

    return session


def save_message(
    db: Session,
    user_id: int,
    thread_id: str,
    role: str,
    content: str,
) -> ChatMessage:
    message = ChatMessage(
        user_id=user_id,
        thread_id=thread_id,
        role=role,
        content=content,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def list_sessions(db: Session, user_id: int) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def list_messages(
    db: Session,
    user_id: int,
    thread_id: str,
) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user_id,
            ChatMessage.thread_id == thread_id,
        )
        .order_by(ChatMessage.id.asc())
        .all()
    )