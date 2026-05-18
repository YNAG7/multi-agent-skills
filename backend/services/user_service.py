# backend/services/user_service.py

from backend.schemas.user import CurrentUser


def current_user_to_dict(user: CurrentUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "disabled": user.disabled,
    }