# backend/repositories/memory_repository.py

from sqlalchemy.orm import Session

from backend.models import UserMemory


def create_memory(
    db: Session,
    user_id: int,
    memory_key: str,
    memory_value: str,
) -> UserMemory:
    memory = UserMemory(
        user_id=user_id,
        memory_key=memory_key,
        memory_value=memory_value,
    )

    db.add(memory)
    db.commit()
    db.refresh(memory)

    return memory


def list_memories(db: Session, user_id: int) -> list[UserMemory]:
    return (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc())
        .all()
    )