# backend/repositories/user_repository.py

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user_record(
    db: Session,
    username: str,
    hashed_password: str,
    nickname: str | None = None,
) -> User:
    user = User(
        username=username,
        nickname=nickname,
        hashed_password=hashed_password,
        disabled=False,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise

    return user