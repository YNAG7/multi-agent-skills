# backend/schemas/chat.py

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    thread_id: str = Field(default="default", description="会话 ID")


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    main_skill: str | None = None
    current_agent: str | None = None


class ChatSessionOut(BaseModel):
    thread_id: str
    title: str | None = None
    created_at: str
    updated_at: str


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: str