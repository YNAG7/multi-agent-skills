# backend/services/agent_service.py

from __future__ import annotations

from typing import Any
from datetime import datetime

from langchain_core.messages import HumanMessage

from agent.graph.builder import build_multi_agent_graph


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

    async def chat(
        self,
        message: str,
        thread_id: str,
    ) -> dict[str, Any]:
        if not self._initialized or self.graph is None:
            raise RuntimeError(
                "AgentService 尚未初始化，请先在 FastAPI lifespan/startup 中调用 await agent_service.init()"
            )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = await self.graph.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=f"[User Message Time: {now}]\n{message}"
                    )
                ]
            },
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
    ):
        """
        新增：流式对话方法
        返回一个异步生成器，不断 yield 文本碎片
        """
        if not self._initialized or self.graph is None:
            raise RuntimeError(
                "AgentService 尚未初始化，请先在 FastAPI lifespan/startup 中调用 await agent_service.init()"
            )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构造输入和配置 (跟原来一模一样)
        inputs = {
            "messages": [
                HumanMessage(
                    content=f"[User Message Time: {now}]\n{message}"
                )
            ]
        }
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # 关键改变：使用 astream_events 替代 ainvoke
        # version="v2" 是 LangChain 官方推荐的事件流版本
        async for event in self.graph.astream_events(
            inputs, 
            config=config, 
            version="v2"
        ):
           if event["event"] == "on_chat_model_stream":
                # 【新增核心逻辑】：揪出当前正在“说话”的节点是谁
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")
                
                # 【过滤器】：如果当前说话的节点是“路由节点”，我们就忽略它，不把它推给前端！
                # 注意：请将 "router" 换成你代码中真实的路由节点名称。
                # 如果你不知道路由节点叫什么名字，你可以反过来写，只允许业务节点输出：
                # if node_name in ["base-assistant", "search-agent"]: 
                
                if node_name != "router":  # <--- 根据你的图结构修改这里
                    
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