# backend/api/auth_api.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.deps import get_current_user
from backend.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from backend.schemas.user import CurrentUser
from backend.services.auth_service import login_user, register_user
from backend.services.user_service import current_user_to_dict


router = APIRouter()


@router.post("/register", response_model=TokenResponse)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
):
    return register_user(db, req)


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
):
    return login_user(db, req)


@router.get("/me")
def me(
    current_user: CurrentUser = Depends(get_current_user),
):
    return current_user_to_dict(current_user)