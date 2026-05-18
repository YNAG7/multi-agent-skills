# backend/api/skill_api.py

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from backend.schemas.user import CurrentUser
from skills.registry import SKILL_REGISTRY
from skills.skills_tools import all_registered_tools


router = APIRouter()


@router.get("")
def list_skills(
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "tool_count": len(skill.tools),
                "needs_time_context": getattr(skill, "needs_time_context", False),
            }
            for skill in SKILL_REGISTRY.values()
        ]
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