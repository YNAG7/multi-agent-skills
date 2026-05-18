from langchain_core.messages import SystemMessage
from model.factory import smart_chat_model
from skills.registry import SKILL_REGISTRY
import datetime


_LLM_WITH_TOOLS_CACHE = {}


def get_llm_with_tools(skill_name: str, skill_tools: list):
    """
    懒加载 bind_tools。

    第一次用到某个 skill 时才 bind_tools。
    后面复用缓存。
    """
    if skill_name not in _LLM_WITH_TOOLS_CACHE:
        _LLM_WITH_TOOLS_CACHE[skill_name] = smart_chat_model.bind_tools(skill_tools)

    return _LLM_WITH_TOOLS_CACHE[skill_name]


async def agent_node(state):
    """
    通用 Agent 节点。

    根据 router 写入的 state["main_skill"] 动态选择 Skill。
    """
    skill_name = state.get("main_skill")

    if not skill_name:
        raise ValueError("state 中缺少 main_skill，router 可能没有正确写入。")

    if skill_name not in SKILL_REGISTRY:
        raise ValueError(f"未知 main_skill: {skill_name}")

    skill_spec = SKILL_REGISTRY[skill_name]

    # 运行时加载当前 skill 的 system prompt
    system_prompt = skill_spec.load_text()


    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    system_prompt += f"\n\n[System Note: 真实时间 {current_time}。"


    # 第一次用到这个 skill 时才 bind_tools
    llm_with_tools = get_llm_with_tools(
        skill_name=skill_name,
        skill_tools=skill_spec.tools,
    )

    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    response = await llm_with_tools.ainvoke(messages)

    return {
        "messages": [response],
        "current_agent": skill_name,
    }