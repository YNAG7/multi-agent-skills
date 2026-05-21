# backend/services/agent_service.py

from __future__ import annotations

from typing import Any
from datetime import datetime
import time

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from backend.core.config import settings
from backend.db.database import SessionLocal
from backend.repositories.monitor_repository import (
    create_agent_run_step,
    create_tool_call,
    finish_tool_call,
    next_step_index,
    update_agent_run_main_skill,
)
from agent.graph.builder import build_multi_agent_graph
from agent.graph.state import RESET_AGENT_RESULTS
from utils.logger_handler import logger


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
        run_id: str | None = None,
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
            },
            "metadata": {
                "run_id": run_id,
            },
        }

        active_tool_calls: dict[str, tuple[int, float, str | None]] = {}

        async for event in self.graph.astream_events(
            inputs, 
            config=config, 
            version="v2"
        ):
            if run_id:
                self._record_stream_event(
                    run_id=run_id,
                    event=event,
                    active_tool_calls=active_tool_calls,
                )

            if event["event"] == "on_chain_end":
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")
                if run_id and node_name == "router":
                    data = event.get("data") or {}
                    output = data.get("output") if isinstance(data, dict) else None
                    tasks = self._extract_tasks_from_output(output)
                    if tasks:
                        skill_names = [
                            task.get("skill")
                            for task in tasks
                            if isinstance(task, dict) and task.get("skill")
                        ]
                        self._update_run_skill(run_id, ",".join(skill_names))

            if event["event"] == "on_chat_model_stream":

                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")
                if node_name != "summarizer":
                    continue            
                
                chunk = event["data"]["chunk"]
                if chunk.content and isinstance(chunk.content, str):
                    yield chunk.content

    @staticmethod
    def _event_payload(event: dict[str, Any]) -> tuple[Any, Any, str | None]:
        data = event.get("data") or {}
        event_name = event.get("event")

        input_data = data.get("input")
        output_data = data.get("output")
        error = None

        if event_name and event_name.endswith("_stream"):
            chunk = data.get("chunk")
            output_data = {
                "chunk": getattr(chunk, "content", None),
            }

        if "error" in data:
            error = str(data.get("error"))

        return input_data, output_data, error

    @staticmethod
    def _extract_tasks_from_output(output: Any) -> list[dict[str, Any]]:
        if hasattr(output, "content"):
            output = getattr(output, "content", None)

        if isinstance(output, str):
            import json

            try:
                output = json.loads(output)
            except Exception:
                return []

        if isinstance(output, dict):
            tasks = output.get("tasks") or output.get("plan") or []

            content = output.get("content")
            if not tasks and isinstance(content, str):
                import json

                try:
                    content = json.loads(content)
                except Exception:
                    content = None

            if not tasks and isinstance(content, dict):
                tasks = content.get("tasks") or content.get("plan") or []
        elif isinstance(output, list):
            tasks = output
        else:
            tasks = []

        return [
            task
            for task in tasks
            if isinstance(task, dict)
        ]

    @staticmethod
    def _record_stream_event(
        run_id: str,
        event: dict[str, Any],
        active_tool_calls: dict[str, tuple[int, float, str | None]],
    ) -> None:
        event_type = event.get("event", "unknown")

        if event_type == "on_chat_model_stream":
            return

        metadata = event.get("metadata") or {}
        node_name = metadata.get("langgraph_node")
        skill_name = AgentService._event_skill(metadata)
        input_data, output_data, error = AgentService._event_payload(event)
        stored_input = input_data if settings.MONITOR_STORE_RAW_EVENTS else None
        stored_output = AgentService._compact_stream_output(
            event_type=event_type,
            node_name=node_name,
            output_data=output_data,
        )
        should_store_step = AgentService._should_store_stream_step(
            event_type=event_type,
            node_name=node_name,
            error=error,
            output_data=stored_output,
        )
        handles_tool_event = event_type in {"on_tool_start", "on_tool_end", "on_tool_error"}
        if not should_store_step and not handles_tool_event:
            return

        db = SessionLocal()
        try:
            step_index = next_step_index(db, run_id)
            if should_store_step:
                create_agent_run_step(
                    db=db,
                    run_id=run_id,
                    step_index=step_index,
                    node_name=node_name,
                    event_type=event_type,
                    input_data=stored_input,
                    output_data=stored_output,
                    error=error,
                )

            if event_type == "on_tool_start":
                tool = create_tool_call(
                    db=db,
                    run_id=run_id,
                    step_index=step_index,
                    tool_name=str(event.get("name") or "tool"),
                    tool_input=input_data,
                    status="running",
                    skill=skill_name,
                )
                active_tool_calls[str(event.get("run_id"))] = (tool.id, time.perf_counter(), skill_name)

            elif event_type in {"on_tool_end", "on_tool_error"}:
                active = active_tool_calls.pop(str(event.get("run_id")), None)
                if active:
                    tool_call_id, started_at, _skill_name = active
                    latency_ms = int((time.perf_counter() - started_at) * 1000)
                    finish_tool_call(
                        db=db,
                        tool_call_id=tool_call_id,
                        tool_output=output_data,
                        status="failed" if event_type == "on_tool_error" else "success",
                        latency_ms=latency_ms,
                    )
        except Exception as e:
            logger.warning(f"[Monitor] stream event save failed: {e}")
        finally:
            db.close()

    @staticmethod
    def _should_store_stream_step(
        event_type: str,
        node_name: str | None,
        error: str | None,
        output_data: Any,
    ) -> bool:
        if settings.MONITOR_STORE_RAW_EVENTS:
            return True

        if error or event_type.endswith("_error"):
            return True

        if event_type == "on_chain_end" and node_name == "router":
            return bool(output_data)

        return False

    @staticmethod
    def _compact_stream_output(
        event_type: str,
        node_name: str | None,
        output_data: Any,
    ) -> Any:
        if settings.MONITOR_STORE_RAW_EVENTS:
            return output_data

        if event_type == "on_chain_end" and node_name == "router":
            tasks = AgentService._extract_tasks_from_output(output_data)
            if tasks:
                return {"tasks": tasks}

        return None

    @staticmethod
    def _event_skill(metadata: dict[str, Any]) -> str | None:
        skill = metadata.get("skill")
        if skill:
            return str(skill)

        checkpoint_ns = metadata.get("checkpoint_ns")
        if isinstance(checkpoint_ns, str) and checkpoint_ns:
            parts = checkpoint_ns.split(":")
            for index, part in enumerate(parts):
                if part == "worker_node" and index + 1 < len(parts):
                    return parts[index + 1]

        task_info = metadata.get("task_info")
        if isinstance(task_info, dict):
            skill = task_info.get("skill")
            if skill:
                return str(skill)

        return None

    @staticmethod
    def _update_run_skill(run_id: str, main_skill: str | None) -> None:
        if not main_skill:
            return

        db = SessionLocal()
        try:
            update_agent_run_main_skill(db, run_id, main_skill)
        except Exception as e:
            logger.warning(f"[Monitor] run skill update failed: {e}")
        finally:
            db.close()
        
        

    async def close(self):
        """
        服务关闭时释放 sqlite 连接。
        """
        if self.conn:
            await self.conn.close()


agent_service = AgentService()
