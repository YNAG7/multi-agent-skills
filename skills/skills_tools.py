from typing import Callable
from skills.registry import SKILL_REGISTRY
from skills.registry import SkillSpec


def get_skill(name: str) -> SkillSpec:
    """
    根据 skill 名称获取 SkillSpec。
    """
    skill = SKILL_REGISTRY[name]

    if not skill.enabled:
        raise KeyError(f"Skill is disabled: {name}")

    return skill


def get_available_skills() -> dict[str, SkillSpec]:
    """
    返回所有可被路由选择的 skill。

    现在已经没有 main / aux 区分了，
    所以这里直接返回所有 Skill。

    如果你以后想排除某些内部 Skill，
    可以在 SkillSpec 里加 enabled / selectable 字段再过滤。
    """
    return {
        k: v
        for k, v in SKILL_REGISTRY.items()
        if v.enabled
    }

def get_available_skill_descriptions() -> dict[str, str]:
    """
    返回 router prompt 使用的简化信息：
    skill_name -> description
    """
    return {
        k: v.description
        for k, v in SKILL_REGISTRY.items()
        if v.enabled
    }


def get_skill_map() -> dict[str, str]:
    """
    返回 skill name -> description。

    给 router prompt 使用。
    """
    return {
        spec.name: spec.description
        for spec in SKILL_REGISTRY.values()
        if spec.enabled
    }


def all_registered_tools() -> list[Callable]:
    """
    返回所有已注册工具。

    ToolNode 需要知道所有可能被调用的工具，
    所以这里仍然要遍历所有 skill.tools。
    """
    tools: list[Callable] = []
    seen: set[str] = set()

    for skill in SKILL_REGISTRY.values():
        if not skill.enabled:
            continue

        for tool in skill.tools:
            tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))

            if tool_name in seen:
                continue

            tools.append(tool)
            seen.add(tool_name)

    return tools


def format_skill_map(skill_map: dict[str, str]) -> str:
    """
    把 name -> description 转成 router 可读文本。
    """
    
    lines = []

    for name, description in skill_map.items():
        lines.append(f"{name}- {description}")

    return "\n\n".join(lines)
