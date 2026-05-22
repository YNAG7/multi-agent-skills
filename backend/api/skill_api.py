# backend/api/skill_api.py

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from backend.deps import get_current_user
from backend.schemas.skill import (
    SkillCreate,
    SkillEnableUpdate,
    SkillImportFromDirectory,
    SkillUpdate,
)
from backend.schemas.user import CurrentUser
from backend.services import skill_service
from skills.skills_tools import all_registered_tools


router = APIRouter()


@router.get("")
def list_skills(
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skills": skill_service.list_skills()
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_skill(
    req: SkillCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skill": await skill_service.create_prompt_skill(req)
    }


@router.post("/import/zip", status_code=status.HTTP_201_CREATED)
async def import_skill_zip(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    return await skill_service.import_skill_zip(file)


@router.post("/import/zip/preview")
async def preview_skill_zip(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    return await skill_service.preview_skill_zip(file)


@router.post("/import/directory", status_code=status.HTTP_201_CREATED)
async def import_skill_directory(
    req: SkillImportFromDirectory,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await skill_service.import_skill_directory(req.source)


@router.post("/reload")
async def reload_skills(
    current_user: CurrentUser = Depends(get_current_user),
):
    await skill_service.reload_runtime()
    return {
        "skills": skill_service.list_skills()
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


@router.get("/{skill_name}")
def skill_detail(
    skill_name: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skill": skill_service.get_skill_detail(skill_name)
    }


@router.patch("/{skill_name}/enabled")
async def set_skill_enabled(
    skill_name: str,
    req: SkillEnableUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skill": await skill_service.set_skill_enabled(skill_name, req.enabled)
    }


@router.patch("/{skill_name}")
async def update_skill(
    skill_name: str,
    req: SkillUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return {
        "skill": await skill_service.update_skill_files(skill_name, req)
    }


@router.delete("/{skill_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_name: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    await skill_service.delete_skill(skill_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
