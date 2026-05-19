from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.constants import Send
from agent.graph.state import AgentState, WorkerState
from agent.graph.nodes import worker_agent_node,summarizer_node
from agent.graph.router import router_node
from skills.registry import SKILL_REGISTRY, inject_mcp_tools_into_registry
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from utils.path_tool import get_abs_path
from skills.skills_tools import all_registered_tools

def tools_condition(state: WorkerState):
    """子图内部的工具判断"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"

async def build_multi_agent_graph():
    await inject_mcp_tools_into_registry(SKILL_REGISTRY)
    tools = all_registered_tools()
    
    # ==========================================
    # 1. 构建子图 (Worker Graph): 隔离每个并发任务
    # ==========================================
    worker_builder = StateGraph(WorkerState)
    worker_builder.add_node("agent", worker_agent_node)
    worker_builder.add_node("tools", ToolNode(tools))

    worker_builder.add_edge(START, "agent")
    worker_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", "__end__": END}
    )
    worker_builder.add_edge("tools", "agent")
    worker_graph = worker_builder.compile()

    # ==========================================
    # 2. 包装子图节点：捕获结果并回传给主图
    # ==========================================
    async def run_worker_subgraph(state: WorkerState):
        # 独立运行子图
        result = await worker_graph.ainvoke(state)
        # 获取子图执行完毕后的最终回复
        final_msg = result["messages"][-1].content
        skill_name = state["task_info"]["skill"]
        # 返回给主图的 agent_results（利用 operator.add 自动聚合成列表）
        return {"agent_results": [f"[{skill_name} 处理结果]:\n{final_msg}"]}

    # ==========================================
    # 3. 主图并行分发逻辑 (Map 过程)
    # ==========================================
    def dispatch_tasks(state: AgentState):
        tasks = state.get("tasks", [])
        if not tasks:
            return "__end__"
        
        # 核心：使用 Send API 动态生成多个并行执行的分支
        return [
            Send("worker_node", {
                "task_info": task,
                # 将主图的历史消息复制给子图提供上下文
                "messages": state["messages"] 
            }) for task in tasks
        ]

    # ==========================================
    # 4. 构建主图 (Main Graph)
    # ==========================================
    builder = StateGraph(AgentState)
    
    builder.add_node("router", router_node)
    builder.add_node("worker_node", run_worker_subgraph) 
    builder.add_node("summarizer", summarizer_node) # 新增：注册汇总节点

    builder.add_edge(START, "router")
    
    # Router 结束后，触发 dispatch_tasks 进行异步 Fan-out
    builder.add_conditional_edges("router", dispatch_tasks, ["worker_node", "__end__"])
    
    # 【核心修改点】
    # 当所有由 Send 拉起的并行 worker_node 执行完毕后，LangGraph 会自动等待它们全部 Fan-in。
    # 然后，我们将流程导向 summarizer 进行最终总结。
    builder.add_edge("worker_node", "summarizer")
    
    # 汇总结束后，整个对话流程才真正结束
    builder.add_edge("summarizer", END)

    # 5. sqlite 会话记忆
    conn = await aiosqlite.connect(get_abs_path("datas/chat_multi_history.db"))
    memory = AsyncSqliteSaver(conn)
    graph = builder.compile(checkpointer=memory)

    return graph, conn, memory