# backend/schemas/user.py

from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    disabled: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    disabled: bool = False