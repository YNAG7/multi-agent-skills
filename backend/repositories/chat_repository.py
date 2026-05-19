# backend/repositories/chat_repository.py

from datetime import datetime
import sqlite3

from sqlalchemy.orm import Session

from backend.models import ChatSession, ChatMessage, ChatThreadSummary
from utils.path_tool import get_abs_path


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


def count_messages(
    db: Session,
    user_id: int,
    thread_id: str,
) -> int:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user_id,
            ChatMessage.thread_id == thread_id,
        )
        .count()
    )


def list_recent_messages(
    db: Session,
    user_id: int,
    thread_id: str,
    limit: int,
) -> list[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user_id,
            ChatMessage.thread_id == thread_id,
        )
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )

    return list(reversed(messages))


def list_messages_for_compression(
    db: Session,
    user_id: int,
    thread_id: str,
    after_id: int,
    before_id: int,
) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user_id,
            ChatMessage.thread_id == thread_id,
            ChatMessage.id > after_id,
            ChatMessage.id <= before_id,
        )
        .order_by(ChatMessage.id.asc())
        .all()
    )


def get_thread_summary(
    db: Session,
    user_id: int,
    thread_id: str,
) -> ChatThreadSummary | None:
    return (
        db.query(ChatThreadSummary)
        .filter(
            ChatThreadSummary.user_id == user_id,
            ChatThreadSummary.thread_id == thread_id,
        )
        .first()
    )


def upsert_thread_summary(
    db: Session,
    user_id: int,
    thread_id: str,
    summary: str,
    last_compressed_message_id: int,
) -> ChatThreadSummary:
    item = get_thread_summary(db=db, user_id=user_id, thread_id=thread_id)

    if item is None:
        item = ChatThreadSummary(
            user_id=user_id,
            thread_id=thread_id,
            summary=summary,
            last_compressed_message_id=last_compressed_message_id,
        )
        db.add(item)
    else:
        item.summary = summary
        item.last_compressed_message_id = last_compressed_message_id
        item.updated_at = datetime.now()

    db.commit()
    db.refresh(item)

    return item


def delete_session(
    db: Session,
    user_id: int,
    thread_id: str,
) -> bool:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.thread_id == thread_id,
        )
        .first()
    )

    if session is None:
        return False

    db.query(ChatMessage).filter(
        ChatMessage.user_id == user_id,
        ChatMessage.thread_id == thread_id,
    ).delete(synchronize_session=False)
    db.query(ChatThreadSummary).filter(
        ChatThreadSummary.user_id == user_id,
        ChatThreadSummary.thread_id == thread_id,
    ).delete(synchronize_session=False)
    db.delete(session)
    db.commit()

    checkpoint_thread_id = f"user_{user_id}:{thread_id}"
    checkpoint_db = get_abs_path("datas/chat_multi_history.db")

    try:
        with sqlite3.connect(checkpoint_db) as conn:
            conn.execute("DELETE FROM checkpoints WHERE thread_id IN (?, ?)", (thread_id, checkpoint_thread_id))
            conn.execute("DELETE FROM writes WHERE thread_id IN (?, ?)", (thread_id, checkpoint_thread_id))
            conn.commit()
    except sqlite3.Error:
        pass

    return True
