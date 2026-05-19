from langchain_core.messages import SystemMessage
from model.factory import smart_chat_model
from skills.registry import SKILL_REGISTRY
import datetime
from agent.graph.state import AgentState

_LLM_WITH_TOOLS_CACHE = {}

def get_llm_with_tools(skill_name: str, skill_tools: list):
    if skill_name not in _LLM_WITH_TOOLS_CACHE:
        _LLM_WITH_TOOLS_CACHE[skill_name] = smart_chat_model.bind_tools(skill_tools)
    return _LLM_WITH_TOOLS_CACHE[skill_name]

async def worker_agent_node(state):
    """
    子图中的 Agent 节点。专注处理单一任务。
    """
    task = state.get("task_info")
    if not task:
        raise ValueError("缺少 task_info。")

    skill_name = task["skill"]
    sub_task_desc = task["sub_task"]
    skill_spec = SKILL_REGISTRY[skill_name]

    if not skill_spec.enabled:
        raise ValueError(f"Skill is disabled: {skill_name}")

    system_prompt = skill_spec.load_text()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 将具体的子任务指令注入系统提示词
    system_prompt += f"\n\n[System Note: 真实时间 {current_time}。]"
    system_prompt += f"\n\n[Your Current Task: {sub_task_desc}]"

    llm_with_tools = get_llm_with_tools(skill_name, skill_spec.tools)

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)

    return {"messages": [response]}

async def summarizer_node(state: AgentState):
    """
    Fan-in 汇总节点 (Reduce)。
    当所有并行的 worker_node 执行完毕后，此节点会被触发。
    """
    results = state.get("agent_results", [])
    
    # 如果没有任何并行结果，直接跳过
    if not results:
        return {"messages": []}

    # 1. 组装汇总 Prompt
    summary_prompt = (
        "你是一个高级多任务协调与汇总专家。\n"
        "为了回答用户的请求，系统已经将任务拆分给多个专业 Agent 并行处理。\n"
        "以下是各个专业 Agent 返回的处理结果：\n\n"
        "====================\n"
    )
    
    for res in results:
        summary_prompt += f"{res}\n--------------------\n"
        
    summary_prompt += (
        "====================\n"
        "请根据上述信息，综合生成一个结构清晰、连贯的最终答复。\n"
        "要求：\n"
        "1. 不要暴露底层是多个 Agent 执行的痕迹（例如不要说“Agent A说...”），要以统一的助手口吻回复。\n"
        "2. 如果各个结果之间有逻辑关联，请平滑过渡。\n"
        "3. 直接回答用户的核心诉求。"
    )

    # 2. 调用大模型进行总结
    # 传入系统提示词以及之前的对话历史（主要是为了让模型知道用户最初问了什么）
    messages = [SystemMessage(content=summary_prompt)] + state["messages"]
    
    response = await smart_chat_model.ainvoke(messages)

    # 3. 将最终的汇总结果作为新消息追加到全局 messages 中
    return {"messages": [response]}
