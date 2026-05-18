# skills/auto_script_loader.py

from __future__ import annotations

import hashlib
import importlib.util
import inspect
from pathlib import Path
from typing import Callable
from utils.logger_handler import logger

from langchain_core.tools import BaseTool, StructuredTool


def _safe_module_name(py_file: Path) -> str:
    """
    根据文件路径生成一个不会冲突的模块名。

    例如：
    skills/file/news_service/scripts/tools.py
    会变成类似：
    skill_script_6a8f3c2d9e
    """
    raw = str(py_file.resolve()).encode("utf-8")
    digest = hashlib.md5(raw).hexdigest()
    return f"skill_script_{digest}"


def _import_py_file(py_file: Path):
    """
    动态 import 一个 Python 文件。

    等价于：
    import skills.file.news_service.scripts.tools

    但这里不要求你的 scripts 目录必须是标准 Python 包。
    """
    module_name = _safe_module_name(py_file)

    spec = importlib.util.spec_from_file_location(module_name, str(py_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载脚本文件: {py_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def _is_langchain_tool(obj) -> bool:
    """
    判断对象是不是 LangChain Tool。

    例如：

    from langchain_core.tools import tool

    @tool
    def get_news(...):
        ...
    """
    return isinstance(obj, BaseTool)


def _is_marked_skill_tool(obj) -> bool:
    """
    判断对象是不是被 @skill_tool 标记过的普通函数。
    """
    return (
        inspect.isfunction(obj)
        and getattr(obj, "_is_skill_tool", False) is True
    )


def _convert_to_structured_tool(func: Callable) -> StructuredTool:
    """
    把普通函数转换成 LangChain StructuredTool。
    """
    description = getattr(func, "_skill_tool_description", "") or func.__doc__ or ""

    return StructuredTool.from_function(
        func=func,
        name=func.__name__,
        description=description,
    )


def _load_tools_from_module(module) -> list:
    """
    从一个 Python 模块里提取工具。

    支持两种方式：

    方式一：模块里定义 TOOL_EXPORTS，只导出指定工具

    TOOL_EXPORTS = [get_news, search_weather]

    方式二：自动扫描模块里所有 @tool 或 @skill_tool 函数
    """
    tools = []

    # 推荐方式：如果脚本里显式写了 TOOL_EXPORTS，就只加载它指定的工具
    if hasattr(module, "TOOL_EXPORTS"):
        for obj in module.TOOL_EXPORTS:
            if _is_langchain_tool(obj):
                tools.append(obj)
            elif _is_marked_skill_tool(obj):
                tools.append(_convert_to_structured_tool(obj))
        return tools

    # 否则自动扫描模块里所有变量
    for _, obj in vars(module).items():
        if _is_langchain_tool(obj):
            tools.append(obj)
        elif _is_marked_skill_tool(obj):
            tools.append(_convert_to_structured_tool(obj))

    return tools


def load_script_tools(skill_dir: str | Path) -> list:
    """
    扫描某个 Skill 文件夹下面的 scripts 目录。

    例如：
    skill_dir = skills/file/news_service

    会扫描：
    skills/file/news_service/scripts/**/*.py
    """
    skill_dir = Path(skill_dir)
    scripts_dir = skill_dir / "scripts"

    if not scripts_dir.exists():
        return []

    all_tools = []
    seen_tool_names = set()

    for py_file in scripts_dir.rglob("*.py"):
        # 跳过 __init__.py 和 _ 开头的内部文件
        if py_file.name == "__init__.py" or py_file.name.startswith("_"):
            continue

        try:
            module = _import_py_file(py_file)
            tools = _load_tools_from_module(module)

            for tool in tools:
                tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", None)

                if not tool_name:
                    continue

                # 防止重复注册同名工具
                if tool_name in seen_tool_names:
                    continue

                all_tools.append(tool)
                seen_tool_names.add(tool_name)

        except Exception as e:
            logger.error(f"[Skill Script Loader] 加载失败: {py_file}")
            logger.error(f"[Skill Script Loader] 错误信息: {e}")

    return all_tools

def load_common_tools(module_path: str = "agent.tools.common_tools") -> list:
    """
    加载程序内部公共工具。

    默认读取：
    agent/tools/common_tools.py

    并从里面拿：
    COMMON_TOOL_EXPORTS
    """
    try:
        module = importlib.import_module(module_path)
    except Exception as e:
        logger.error(f"[Common Tool Loader] 加载公共工具模块失败: {module_path}, error={e}")
        return []

    exports = getattr(module, "COMMON_TOOL_EXPORTS", [])

    tools = []

    for obj in exports:
        if isinstance(obj, BaseTool):
            tools.append(obj)
        else:
            logger.warning(f"[Common Tool Loader] 跳过非 LangChain Tool: {obj}")

    

    return tools