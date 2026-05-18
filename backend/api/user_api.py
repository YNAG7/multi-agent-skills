# backend/api/user_api.py

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from backend.schemas.user import CurrentUser
from backend.services.user_service import current_user_to_dict


router = APIRouter()


@router.get("/me")
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
):
    return current_user_to_dict(current_user)