# skills/mcp_tool_loader.py

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any
import traceback
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from utils.logger_handler import logger
from utils.path_tool import get_abs_path


def _resolve_value(value: Any, project_root: str) -> Any:
    """
    递归替换配置里的变量。

    支持：
    - ${PROJECT_ROOT}
    - ${NEWS_MCP_TOKEN}
    - ${任意环境变量名}
    """
    if isinstance(value, str):
        value = value.replace("${PROJECT_ROOT}", project_root)

        for key, env_value in os.environ.items():
            value = value.replace("${" + key + "}", env_value)

        return value

    if isinstance(value, list):
        return [_resolve_value(v, project_root) for v in value]

    if isinstance(value, dict):
        return {k: _resolve_value(v, project_root) for k, v in value.items()}

    return value


def _normalize_mcp_config(
    mcp_servers: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """
    处理 skill.json 里的 MCP 配置。

    远端 MCP 示例：
    {
      "news_tools": {
        "transport": "streamable_http",
        "url": "https://xxx.com/mcp",
        "headers": {
          "Authorization": "Bearer ${NEWS_MCP_TOKEN}"
        }
      }
    }
    """
    project_root = str(Path(get_abs_path(".")).resolve())
    config = copy.deepcopy(mcp_servers)
    return _resolve_value(config, project_root)


def _short_tool_name(tool_name: str) -> str:
    """
    兼容不同工具命名方式。

    例如：
    - get_news
    - news_tools__get_news
    - news_tools.get_news
    """
    return tool_name.split("__")[-1].split(".")[-1]


def filter_mcp_tools(
    tools: list[BaseTool],
    allowlist: list[str] | None = None,
) -> list[BaseTool]:
    """
    根据 mcp_tool_allowlist 过滤 MCP 工具。

    allowlist 为空时，默认不过滤。
    """
    if not allowlist:
        return tools

    allowset = set(allowlist)
    result = []
    seen = set()

    for tool in tools:
        name = getattr(tool, "name", "")

        if not name:
            continue

        short_name = _short_tool_name(name)

        if name not in allowset and short_name not in allowset:
            continue

        if name in seen:
            continue

        result.append(tool)
        seen.add(name)

    return result


async def load_mcp_tools_from_config(
    mcp_servers: dict[str, dict[str, Any]],
    allowlist: list[str] | None = None,
) -> list[BaseTool]:
    """
    根据 skill.json 中的 mcp_servers 加载远端 MCP tools。
    """
    if not mcp_servers:
        return []

    try:
        normalized_config = _normalize_mcp_config(mcp_servers)

        client = MultiServerMCPClient(normalized_config)

        tools = await client.get_tools()

        tools = filter_mcp_tools(
            tools=tools,
            allowlist=allowlist or [],
        )

        logger.info(
            "[MCP Tool Loader] 已加载 MCP tools: "
            + str([getattr(t, "name", str(t)) for t in tools])
        )

        return tools

    except* Exception as eg:
        print("\n[MCP Tool Loader] 捕获到 ExceptionGroup，子异常如下：")

        for i, exc in enumerate(eg.exceptions, start=1):
            print(f"\n========== 子异常 {i} ==========")
            print(type(exc).__name__)
            print(str(exc))
            traceback.print_exception(type(exc), exc, exc.__traceback__)

        raise