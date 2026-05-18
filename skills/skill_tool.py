# skills/skill_tool.py

from functools import wraps


def skill_tool(description: str = ""):
    """
    给普通 Python 函数打标记。

    被 @skill_tool 装饰的函数，会在扫描 scripts 时
    自动转换成 LangChain 的 StructuredTool。

    用法：

    @skill_tool(description="获取新闻")
    def fetch_news(query: str) -> list:
        ...
    """

    def decorator(func):
        func._is_skill_tool = True
        func._skill_tool_description = description or func.__doc__ or ""
        return func

    return decorator