# agent/graph/select_router.py

from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, Field, ValidationError

from utils.prompt_loader import load_router_prompt
from model.factory import cheap_chat_model
from skills.skills_tools import format_skill_map, get_available_skill_descriptions


# 读取可选 skill
main_skills_dict = get_available_skill_descriptions()
main_block = format_skill_map(main_skills_dict)
main_names = list(main_skills_dict.keys())

print(main_block)


# 动态构造枚举
MainSkillEnum = Enum(
    "MainSkillEnum",
    {k: k for k in main_skills_dict.keys()}
)


class SkillRoute(BaseModel):
    main_skill: MainSkillEnum = Field(
        ...,
        description="本轮任务唯一选择的主 skill，只能是候选 skill 名称之一。"
    )

    reason: str = Field(
        ...,
        description="简要说明为什么选择这个 skill。"
    )


def _clean_json_text(text: str) -> str:
    """
    清理模型返回的 JSON 文本。
    """
    text = text.strip()

    # 去掉 markdown 代码块
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return text


def _extract_json_object(text: str) -> str | None:
    """
    从模型输出中提取 JSON 对象字符串。
    """
    text = _clean_json_text(text)

    # 如果本身就是 JSON
    if text.startswith("{") and text.endswith("}"):
        return text

    # 从长文本里提取第一个 {...}
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    return None


def _parse_skill_route(raw_text: str) -> SkillRoute | None:
    """
    用 Pydantic schema 校验模型输出。
    """
    json_str = _extract_json_object(raw_text)

    if not json_str:
        return None

    try:
        data = json.loads(json_str)
        return SkillRoute.model_validate(data)
    except ValidationError as e:
        print(f"[Router Validation Error] {e}")
        return None
    except Exception as e:
        print(f"[Router JSON Parse Error] {e}")
        return None


def _fallback_extract_skill(raw_text: str) -> str:
    """
    最后兜底：从文本里找 skill 名称。
    """
    raw_text = raw_text.strip()

    if raw_text in main_skills_dict:
        return raw_text

    for name in main_names:
        if name in raw_text:
            return name

    return "base-assistant"


def select_skill(user_text: str) -> str:
    """
    使用结构化 JSON schema 做路由。

    注意：
    这里不使用 with_structured_output。
    原因是 qwen-turbo 可能返回普通 JSON 文本，而不是 tool_call。
    我们仍然使用 Pydantic SkillRoute 做结构化校验。
    """

    prompt = load_router_prompt().format(
        last_msg=user_text,
        main_block=main_block,
        main_names=", ".join(main_names),
    )

    res = cheap_chat_model.invoke(prompt)

    raw_text = getattr(res, "content", str(res)).strip()

    print(f"[Router Raw] {raw_text}")

    route = _parse_skill_route(raw_text)

    if route is not None:
        main_skill = route.main_skill.value
        print(f"[Router Selected] {main_skill}")
        print(f"[Router Reason] {route.reason}")
        return main_skill

    fallback_skill = _fallback_extract_skill(raw_text)

    print(f"[Router Fallback Selected] {fallback_skill}")

    return fallback_skill