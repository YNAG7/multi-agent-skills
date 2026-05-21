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
from utils.logger_handler import logger


def _safe_message_payload(message):
    payload = {
        "type": message.__class__.__name__,
        "content": getattr(message, "content", None),
    }

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = tool_calls

    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id

    name = getattr(message, "name", None)
    if name:
        payload["name"] = name

    return payload


def _final_message_payload(messages):
    for message in reversed(messages):
        if message.__class__.__name__ == "ToolMessage":
            continue
        return _safe_message_payload(message)
    return None


def _record_worker_trace(config, skill_name: str, task_info: dict, result: dict | None = None, error: Exception | None = None):
    metadata = (config or {}).get("metadata") or {}
    run_id = metadata.get("run_id")
    if not run_id:
        return

    try:
        from backend.db.database import SessionLocal
        from backend.core.config import settings
        from backend.repositories.monitor_repository import (
            create_agent_run_step,
            create_tool_call,
            finish_tool_call,
            next_step_index,
        )

        db = SessionLocal()

        try:
            create_agent_run_step(
                db=db,
                run_id=run_id,
                step_index=next_step_index(db, run_id),
                node_name="worker_node",
                event_type="worker_start",
                input_data={
                    "skill": skill_name,
                    "task_info": task_info,
                },
            )

            if error is not None:
                create_agent_run_step(
                    db=db,
                    run_id=run_id,
                    step_index=next_step_index(db, run_id),
                    node_name="worker_node",
                    event_type="worker_error",
                    output_data={"skill": skill_name},
                    error=str(error),
                )
                return

            messages = (result or {}).get("messages", [])
            if settings.MONITOR_CAPTURE_OBSERVED_TOOLS:
                for message in messages:
                    tool_calls = getattr(message, "tool_calls", None) or []
                    for tool_call in tool_calls:
                        if isinstance(tool_call, dict):
                            tool_name = tool_call.get("name")
                            tool_args = tool_call.get("args")
                        else:
                            tool_name = getattr(tool_call, "name", None)
                            tool_args = getattr(tool_call, "args", None)

                        if not tool_name:
                            continue

                        tool = create_tool_call(
                            db=db,
                            run_id=run_id,
                            step_index=next_step_index(db, run_id),
                            tool_name=str(tool_name),
                            tool_input=tool_args,
                            status="observed",
                            skill=skill_name,
                        )
                        finish_tool_call(
                            db=db,
                            tool_call_id=tool.id,
                            status="observed",
                        )

                    if message.__class__.__name__ == "ToolMessage":
                        tool = create_tool_call(
                            db=db,
                            run_id=run_id,
                            step_index=next_step_index(db, run_id),
                            tool_name=str(getattr(message, "name", None) or getattr(message, "tool_call_id", "tool")),
                            status="success",
                            skill=skill_name,
                        )
                        finish_tool_call(
                            db=db,
                            tool_call_id=tool.id,
                            tool_output=_safe_message_payload(message),
                            status="success",
                        )

            create_agent_run_step(
                db=db,
                run_id=run_id,
                step_index=next_step_index(db, run_id),
                node_name="worker_node",
                event_type="worker_end",
                output_data={
                    "skill": skill_name,
                    "messages": [_final_message_payload(messages)],
                },
            )
        finally:
            db.close()
    except Exception as trace_error:
        logger.warning(f"[Monitor] worker trace save failed: {trace_error}")


def tools_condition(state: WorkerState):
    """子图内部的工具判断"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"

async def build_multi_agent_graph():
    await inject_mcp_tools_into_registry(SKILL_REGISTRY)
    worker_graph_cache = {}
    
    # ==========================================
    # 1. 构建子图 (Worker Graph): 隔离每个并发任务
    # ==========================================
    def get_worker_graph(skill_name: str):
        if skill_name in worker_graph_cache:
            return worker_graph_cache[skill_name]

        skill_spec = SKILL_REGISTRY[skill_name]
        worker_builder = StateGraph(WorkerState)
        worker_builder.add_node("agent", worker_agent_node)
        worker_builder.add_node("tools", ToolNode(skill_spec.tools))

        worker_builder.add_edge(START, "agent")
        worker_builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", "__end__": END}
        )
        worker_builder.add_edge("tools", "agent")
        worker_graph_cache[skill_name] = worker_builder.compile()
        return worker_graph_cache[skill_name]

    # ==========================================
    # 2. 包装子图节点：捕获结果并回传给主图
    # ==========================================
    async def run_worker_subgraph(state: WorkerState, config=None):
        skill_name = state.get("task_info", {}).get("skill", "未知技能")
        if not skill_name or skill_name not in SKILL_REGISTRY or not SKILL_REGISTRY[skill_name].enabled:
            return {"agent_results": [f"[Skill unavailable]: {skill_name or 'none'}"]}

        try:
            # 独立运行子图
            worker_graph = get_worker_graph(skill_name)
            subgraph_config = {
                "recursion_limit": 30,
                "metadata": {
                    **((config or {}).get("metadata") or {}),
                    "skill": skill_name,
                    "task_info": state.get("task_info", {}),
                },
            }
            result = await worker_graph.ainvoke(state,config=subgraph_config)
            _record_worker_trace(config, skill_name, state.get("task_info", {}), result=result)
            final_msg = result["messages"][-1].content
            return {"agent_results": [f"[{skill_name} 成功处理]:\n{final_msg}"]}
        except Exception as e:
            _record_worker_trace(config, skill_name, state.get("task_info", {}), error=e)
            logger.warning(f"[⚠️ Worker 异常] {skill_name} 执行失败: {e}")
            return {"agent_results": [f"[{skill_name} 处理失败]:\n系统执行该子任务时遇到异常（{str(e)}），请忽略此部分结果并向用户致歉。"]}

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
                "messages": []
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
