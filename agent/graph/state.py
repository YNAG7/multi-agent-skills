import operator
from typing import Annotated, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

# --- 主图状态 ---
class AgentState(TypedDict, total=False):
    # 用户的全局对话历史
    messages: Annotated[list, add_messages]
    # Router 拆解出的并发任务列表
    tasks: List[Dict[str, str]]
    # 异步并发执行的结果汇总（使用 operator.add 将所有并行跑完的结果拼接成列表）
    agent_results: Annotated[list, operator.add]

# --- 子图状态 (单个并发 Worker) ---
class WorkerState(TypedDict, total=False):
    # 子图内部的局部消息流，避免与主图及其他并发任务冲突
    messages: Annotated[list, add_messages]
    # 当前 worker 负责的具体任务信息
    task_info: Dict[str, str]