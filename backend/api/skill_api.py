# backend/api/skill_api.py

from pathlib import Path
import re

import yaml
from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_current_user
from backend.schemas.skill import SkillCreate
from backend.schemas.user import CurrentUser
from skills.registry import (
    SKILL_REGISTRY,
    inject_mcp_tools_into_registry,
    reload_skill_registry,
)
from skills.skills_tools import all_registered_tools
from utils.path_tool import get_abs_path


router = APIRouter()


def _skill_payload(skill):
    return {
        "name": skill.name,
        "description": skill.description,
        "tool_count": len(skill.tools),
        "needs_time_context": getattr(skill, "needs_time_context", False),
        "skill_path": skill.skill_path,
    }


def _normalize_skill_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-_")
    return normalized


def _skills_file_root() -> Path:
    return Path(get_abs_path("skills/file")).resolve()


def _write_skill_file(req: SkillCreate, skill_name: str) -> Path:
    root = _skills_file_root()
    skill_dir = (root / skill_name).resolve()

    if root not in skill_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid skill name")

    if skill_dir.exists():
        raise HTTPException(status_code=409, detail="Skill already exists")

    skill_dir.mkdir(parents=True, exist_ok=False)

    meta = {
        "name": skill_name,
        "description": req.description.strip(),
    }

    if req.needs_time_context:
        meta["needs_time_context"] = True

    yaml_text = yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
    )

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\n{yaml_text}---\n\n{req.content.strip()}\n",
        encoding="utf-8",
    )

    return skill_md


@router.get("")
def list_skills(
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skills": [_skill_payload(skill) for skill in SKILL_REGISTRY.values()]
    }


@router.post("", status_code=201)
async def create_skill(
    req: SkillCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    skill_name = _normalize_skill_name(req.name)

    if not skill_name:
        raise HTTPException(
            status_code=400,
            detail="Skill name must contain letters, numbers, '-' or '_'",
        )

    if skill_name in SKILL_REGISTRY:
        raise HTTPException(status_code=409, detail="Skill already exists")

    _write_skill_file(req, skill_name)
    reload_skill_registry()
    await inject_mcp_tools_into_registry()

    skill = SKILL_REGISTRY.get(skill_name)
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill was created but not loaded")

    return {
        "skill": _skill_payload(skill)
    }


@router.get("/tools")
def list_tools(
    current_user: CurrentUser = Depends(get_current_user),
):
    tools = all_registered_tools()

    return {
        "tools": [
            {
                "name": getattr(tool, "name", str(tool)),
                "description": getattr(tool, "description", ""),
            }
            for tool in tools
        ]
    }
