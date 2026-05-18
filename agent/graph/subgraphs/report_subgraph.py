from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent.graph.nodes import report_agent_node
from agent.graph.tools import REPORT_TOOLS

class ReportSubgraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    report_context: str

def build_report_subgraph():
    builder = StateGraph(ReportSubgraphState)

    builder.add_node("report_agent", report_agent_node)
    builder.add_node("report_tools", ToolNode(REPORT_TOOLS))

    builder.add_edge(START, "report_agent")

    builder.add_conditional_edges(
        "report_agent",
        tools_condition,
        {
            "tools": "report_tools",
            "__end__": END,
        },
    )
    builder.add_edge("report_tools", "report_agent")

    return builder.compile()