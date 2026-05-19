# skills/registry.py
from __future__ import annotations
import json
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from skills.auto_script_loader import load_script_tools,load_common_tools
from skills.mcp_tool_loader import load_mcp_tools_from_config

@dataclass
class SkillSpec:
    name: str
    description: str
    skill_path: str

    # 新增：记录 skill 文件夹路径
    skill_dir: str

    tools: list[Callable] = field(default_factory=list)
    is_workflow: bool = False
    workflow_runner: Optional[Callable] = None
    needs_time_context: bool = False
    
    # 新增：远端 MCP 配置
    mcp_servers: dict = field(default_factory=dict)
    mcp_tool_allowlist: list[str] = field(default_factory=list)

    _prompt_content: str = field(default="", init=False, repr=False)

    def load_text(self) -> str:
        return self._prompt_content

    def load_runtime_summary(self) -> str:
        text = self._prompt_content
        marker = "# Summary For Runtime"

        if marker not in text:
            return text

        section = text.split(marker, 1)[1]
        next_heading = section.find("\n# ")

        if next_heading != -1:
            section = section[:next_heading]

        return section.strip()

def dedupe_tools(tools: list) -> list:
    seen = set()
    result = []

    for tool in tools:
        name = getattr(tool, "name", None)

        if not name:
            continue

        if name in seen:
            continue

        result.append(tool)
        seen.add(name)

    return result

def load_skill_json(skill_dir: Path) -> dict:
    """
    读取 skill 目录下的 skill.json。
    不存在则返回空 dict。
    """
    json_path = skill_dir / "skill.json"

    if not json_path.exists():
        return {}

    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"[Skill Registry] skill.json 解析失败: {json_path}, error={e}")
        return {}


def build_skill_registry(skills_root: str = "skills") -> dict[str, SkillSpec]:
    """
    自动构建 Skill 注册表。

    功能：
    1. 自动递归扫描 skills/**/SKILL.md
    2. 读取 SKILL.md 的 YAML frontmatter
    3. 自动扫描每个 Skill 目录下的 scripts/*.py
    4. 把 scripts 里的工具注册到对应 Skill
    """
    registry: dict[str, SkillSpec] = {}
    base_path = Path(get_abs_path(skills_root))

    if not base_path.exists():
        return registry
    
    common_tools = load_common_tools()

    for md_file in base_path.rglob("SKILL.md"):
        raw_text = md_file.read_text(encoding="utf-8")

        meta = {}
        content = raw_text

        # 解析 YAML frontmatter
        if raw_text.startswith("---"):
            parts = raw_text.split("---", 2)

            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                content = parts[2].strip()

        # skill_dir 就是 SKILL.md 所在的文件夹
        skill_dir = md_file.parent
        
        # 读取 skill.json
        json_meta = load_skill_json(skill_dir)

        # 优先使用 YAML 中的 name，其次 skill.json，最后目录名
        name = meta.get("name") or json_meta.get("name") or skill_dir.name

        # 自动扫描该 Skill 下的 scripts
        script_tools = load_script_tools(skill_dir)

        spec = SkillSpec(
            name=name,
            description=meta.get("description", "暂无描述"),
            skill_path=str(md_file),
            skill_dir=str(skill_dir),
            tools=dedupe_tools(script_tools + common_tools),
            is_workflow=meta.get("is_workflow", False),
            needs_time_context=meta.get(
                "needs_time_context",
                json_meta.get("needs_time_context", False)
            ),
            # 新增：远端 MCP 配置
            mcp_servers=json_meta.get("mcp_servers", {}),
            mcp_tool_allowlist=json_meta.get("mcp_tool_allowlist", []),
        )

        spec._prompt_content = content

        registry[name] = spec

        print(
            f"[Skill Registry] 已加载 Skill: {name}, "
            f"tools={ [getattr(t, 'name', str(t)) for t in spec.tools] }"
        )

    return registry

async def inject_mcp_tools_into_registry(
    registry: dict[str, SkillSpec] | None = None,
) -> dict[str, SkillSpec]:
    """
    遍历所有 SkillSpec。

    如果 skill.json 里配置了远端 mcp_servers，
    就连接远端 MCP Server，加载 tools，
    然后追加到 skill.tools。
    """
    registry = registry or SKILL_REGISTRY

    for skill in registry.values():
        if not skill.mcp_servers:
            continue

        mcp_tools = await load_mcp_tools_from_config(
            mcp_servers=skill.mcp_servers,
            allowlist=skill.mcp_tool_allowlist,
        )

        if not mcp_tools:
            continue

        skill.tools = dedupe_tools(skill.tools + mcp_tools)

        logger.info(
            f"[Skill Registry] 已为 Skill 注入远端 MCP Tools: {skill.name}, "
            f"mcp_tools={[getattr(t, 'name', str(t)) for t in mcp_tools]}"
        )

    return registry

# 初始化全局注册表
SKILL_REGISTRY = build_skill_registry()


def reload_skill_registry(skills_root: str = "skills") -> dict[str, SkillSpec]:
    """
    Re-scan skills from disk and refresh the existing registry object in place.

    Several modules import SKILL_REGISTRY directly, so mutating the dict keeps
    those references current after a skill is created from the API.
    """
    refreshed = build_skill_registry(skills_root)
    SKILL_REGISTRY.clear()
    SKILL_REGISTRY.update(refreshed)
    return SKILL_REGISTRY
