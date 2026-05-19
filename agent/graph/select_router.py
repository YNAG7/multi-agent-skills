# agent/graph/select_router.py

from __future__ import annotations

import json
import re
from typing import List

from pydantic import BaseModel, Field, ValidationError

from model.factory import cheap_chat_model
from skills.skills_tools import format_skill_map, get_available_skill_descriptions
from utils.prompt_loader import load_router_prompt


class TaskItem(BaseModel):
    skill: str = Field(..., description="Skill name for this sub task.")
    sub_task: str = Field(..., description="Concrete sub task instruction.")


class SkillRoute(BaseModel):
    plan: List[TaskItem] = Field(
        ...,
        description="A task plan. Use a single item when only one task is needed.",
    )
    reason: str = Field(..., description="Brief routing reason.")


def _get_skill_context() -> tuple[dict[str, str], str, list[str]]:
    skills_dict = get_available_skill_descriptions()
    skills_block = format_skill_map(skills_dict)
    skill_names = list(skills_dict.keys())
    return skills_dict, skills_block, skill_names


def _clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return text


def _extract_json_object(text: str) -> str | None:
    text = _clean_json_text(text)

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    return None


def _parse_skill_route(
    raw_text: str,
    valid_skill_names: list[str],
) -> SkillRoute | None:
    json_str = _extract_json_object(raw_text)

    if not json_str:
        return None

    try:
        data = json.loads(json_str)
        route = SkillRoute.model_validate(data)
        valid_names = set(valid_skill_names)

        for item in route.plan:
            if item.skill not in valid_names:
                print(f"[Router Validation Error] Unknown skill: {item.skill}")
                return None

        return route
    except ValidationError as e:
        print(f"[Router Validation Error] {e}")
        return None
    except Exception as e:
        print(f"[Router JSON Parse Error] {e}")
        return None


def _fallback_extract_skill(
    raw_text: str,
    skills_dict: dict[str, str],
    skill_names: list[str],
) -> str:
    raw_text = raw_text.strip()

    if raw_text in skills_dict:
        return raw_text

    for name in skill_names:
        if name in raw_text:
            return name

    if "base-assistant" in skills_dict:
        return "base-assistant"

    return skill_names[0] if skill_names else ""


def select_skill(user_text: str) -> list[dict[str, str]]:
    skills_dict, skills_block, skill_names = _get_skill_context()

    prompt = load_router_prompt().format(
        last_msg=user_text,
        main_block=skills_block,
        main_names=", ".join(skill_names),
    )

    res = cheap_chat_model.invoke(prompt)
    raw_text = getattr(res, "content", str(res)).strip()

    print(f"[Router Raw] {raw_text}")

    route = _parse_skill_route(raw_text, skill_names)

    if route is not None:
        tasks_list = [
            {"skill": item.skill, "sub_task": item.sub_task}
            for item in route.plan
        ]
        print(f"[Router Selected Plan] {tasks_list}")
        return tasks_list

    fallback_skill = _fallback_extract_skill(raw_text, skills_dict, skill_names)
    print(f"[Router Fallback Selected] {fallback_skill}")

    return [{"skill": fallback_skill, "sub_task": user_text}]
