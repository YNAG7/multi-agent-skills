# backend/services/agent_service.py

from __future__ import annotations

from typing import Any
from datetime import datetime

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from agent.graph.builder import build_multi_agent_graph
from agent.graph.state import RESET_AGENT_RESULTS


class AgentService:
    def __init__(self):
        self.graph = None
        self.conn = None
        self.memory = None
        self._initialized = False

    async def init(self):
        """
        异步初始化 Agent Graph。
        必须在 FastAPI startup/lifespan 中调用。
        """
        if self._initialized:
            return

        self.graph, self.conn, self.memory = await build_multi_agent_graph()
        self._initialized = True

    async def reload(self):
        """
        Rebuild the LangGraph runtime after skills/tools change on disk.
        """
        try:
            from agent.graph.nodes import _LLM_WITH_TOOLS_CACHE

            _LLM_WITH_TOOLS_CACHE.clear()
        except Exception:
            pass

        new_graph, new_conn, new_memory = await build_multi_agent_graph()

        old_conn = self.conn
        self.graph = new_graph
        self.conn = new_conn
        self.memory = new_memory
        self._initialized = True

        if old_conn:
            await old_conn.close()

    @staticmethod
    def _build_graph_input(message: str) -> dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                HumanMessage(content=f"[User Message Time: {now}]\n{message}"),
            ],
            "tasks": [],
            "agent_results": [RESET_AGENT_RESULTS],
        }

    async def chat(
        self,
        message: str,
        thread_id: str,
    ) -> dict[str, Any]:
        if not self._initialized or self.graph is None:
            raise RuntimeError(
                "AgentService 尚未初始化，请先在 FastAPI lifespan/startup 中调用 await agent_service.init()"
            )

        result = await self.graph.ainvoke(
            self._build_graph_input(message),
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            },
        )

        last_msg = result["messages"][-1]

        return {
            "answer": getattr(last_msg, "content", str(last_msg)),
            "thread_id": thread_id,
            "main_skill": result.get("main_skill"),
            "current_agent": result.get("current_agent"),
        }
    
    async def stream_chat(
        self,
        message: str,
        thread_id: str,
        context_text: str | None = None,
    ):
        """
        新增：流式对话方法
        返回一个异步生成器，不断 yield 文本碎片
        """
        if not self._initialized or self.graph is None:
            raise RuntimeError(
                "AgentService 尚未初始化，请先在 FastAPI lifespan/startup 中调用 await agent_service.init()"
            )

        prompt_text = context_text or message

        inputs = self._build_graph_input(prompt_text)
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        async for event in self.graph.astream_events(
            inputs, 
            config=config, 
            version="v2"
        ):
           if event["event"] == "on_chat_model_stream":

                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")
                if node_name != "summarizer":
                    continue            
                
                chunk = event["data"]["chunk"]
                if chunk.content and isinstance(chunk.content, str):
                    yield chunk.content
        
        

    async def close(self):
        """
        服务关闭时释放 sqlite 连接。
        """
        if self.conn:
            await self.conn.close()


agent_service = AgentService()
