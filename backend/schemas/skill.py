from typing import Any

from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    needs_time_context: bool = False
    skill_json: dict[str, Any] | None = None


class SkillUpdate(BaseModel):
    skill_md: str = Field(..., min_length=1)
    skill_json: dict[str, Any] = Field(default_factory=dict)


class SkillOut(BaseModel):
    name: str
    description: str
    tool_count: int
    needs_time_context: bool = False
    skill_path: str | None = None
    skill_dir: str | None = None
    has_mcp: bool = False
    enabled: bool = True
    degraded: bool = False
    load_errors: list[str] = Field(default_factory=list)
    protected: bool = False


class SkillImportFromDirectory(BaseModel):
    source: str = Field(..., min_length=1, max_length=200)


class SkillEnableUpdate(BaseModel):
    enabled: bool


class SkillImportPreview(BaseModel):
    name: str
    description: str
    tool_count: int = 0
    has_mcp: bool = False
    enabled: bool = True
    degraded: bool = False
    load_errors: list[str] = Field(default_factory=list)


class SkillDetail(SkillOut):
    skill_md: str = ""
    skill_json: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, str]] = Field(default_factory=list)
    mcp_servers: dict[str, Any] = Field(default_factory=dict)
    mcp_tool_allowlist: list[str] = Field(default_factory=list)
