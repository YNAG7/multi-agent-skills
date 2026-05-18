from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from agent.graph.state import AgentState
from agent.graph.nodes import agent_node
from skills.registry import SKILL_REGISTRY,inject_mcp_tools_into_registry
from agent.graph.router import router_node
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from utils.path_tool import get_abs_path
from skills.skills_tools import all_registered_tools

def tools_condition(state: AgentState):
    """
    判断是否需要调用工具。
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "__end__"


async def build_multi_agent_graph():
    
    await inject_mcp_tools_into_registry(SKILL_REGISTRY)
    
    tools = all_registered_tools()

    print("\n[Agent Runtime] 当前所有已注册工具：")
    
    builder = StateGraph(AgentState)

    # 1. 路由节点：只负责判断 main_skill
    builder.add_node("router", router_node)

    # 2. 统一 Agent 节点：运行时根据 main_skill 选择 Skill
    builder.add_node("agent", agent_node)

    builder.add_node("tools", ToolNode(tools))

    # 4. 边
    builder.add_edge(START, "router")
    builder.add_edge("router", "agent")

    # 5. agent 执行完后，判断是否调用工具
    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    # 6. 工具执行完后，回到 agent
    builder.add_edge("tools", "agent")

    # 7. sqlite 会话记忆
    conn = await aiosqlite.connect(
        get_abs_path("datas/chat_multi_history.db")
    )
    memory = AsyncSqliteSaver(conn)

    graph = builder.compile(checkpointer=memory)

    return graph, conn, memory