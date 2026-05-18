from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # ① 保存完整消息流，LangGraph 会自动把新消息追加进去
    messages: Annotated[list, add_messages]

    # ③ 当前请求的主 skill
    main_skill: str
    
    # 当前正在执行的 agent，用于 tool 调用后跳回
    current_agent: str

