# backend/services/auth_service.py

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.core.config import settings
from backend.repositories.user_repository import (
    create_user_record,
    get_user_by_username,
)
from backend.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def register_user(db: Session, req: RegisterRequest) -> TokenResponse:
    hashed_password = hash_password(req.password)

    try:
        user = create_user_record(
            db=db,
            username=req.username,
            hashed_password=hashed_password,
            nickname=req.nickname,
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
        }
    )

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "disabled": user.disabled,
            "is_admin": user.username in settings.ADMIN_USERNAMES,
        },
    )


def login_user(db: Session, req: LoginRequest) -> TokenResponse:
    user = get_user_by_username(db, req.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用",
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
        }
    )

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "disabled": user.disabled,
            "is_admin": user.username in settings.ADMIN_USERNAMES,
        },
    )
