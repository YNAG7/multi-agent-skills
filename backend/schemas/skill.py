from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    needs_time_context: bool = False


class SkillOut(BaseModel):
    name: str
    description: str
    tool_count: int
    needs_time_context: bool = False
    skill_path: str | None = None
