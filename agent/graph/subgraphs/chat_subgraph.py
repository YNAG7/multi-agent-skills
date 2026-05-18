from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent.graph.nodes import chat_agent_node
from agent.graph.tools import CHAT_TOOLS

class ChatSubgraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    chat_context: str

def build_chat_subgraph():
    builder = StateGraph(ChatSubgraphState)

    builder.add_node("chat_agent", chat_agent_node)
    builder.add_node("chat_tools", ToolNode(CHAT_TOOLS))

    builder.add_edge(START, "chat_agent")

    builder.add_conditional_edges(
        "chat_agent",
        tools_condition,
        {
            "tools": "chat_tools",
            "__end__": END,
        },
    )
    builder.add_edge("chat_tools", "chat_agent")

    return builder.compile()