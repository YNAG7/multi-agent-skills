from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.core.config import settings
from utils.logger_handler import logger
from utils.path_tool import get_abs_path


class Mem0Service:
    def __init__(self):
        self._memory = None
        self._available = False

    def _get_memory(self):
        if not settings.MEMORY_ENABLED:
            return None

        if self._memory is not None:
            return self._memory

        mem0_dir = Path(get_abs_path(settings.MEM0_DIR)).resolve()
        mem0_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MEM0_DIR", str(mem0_dir))

        try:
            from mem0 import Memory

            self._memory = Memory.from_config(
                {
                    "vector_store": {
                        "provider": "qdrant",
                        "config": {
                            "path": str(mem0_dir / "qdrant"),
                        },
                    },
                    "history_db_path": str(mem0_dir / "history.db"),
                }
            )
            self._available = True
        except Exception as e:
            self._available = False
            logger.warning(f"[Mem0] disabled because initialization failed: {e}")
            return None

        return self._memory

    def search(self, user_id: int, query: str, limit: int | None = None) -> list[str]:
        memory = self._get_memory()
        if memory is None or not query.strip():
            return []

        try:
            result = memory.search(
                query=query,
                top_k=limit or settings.MEMORY_TOP_K,
                filters={"user_id": str(user_id)},
            )
        except Exception as e:
            logger.warning(f"[Mem0] search failed: {e}")
            return []

        return self._normalize_search_results(result)

    def add_turn(
        self,
        user_id: int,
        thread_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        memory = self._get_memory()
        if memory is None or not user_message.strip() or not assistant_message.strip():
            return

        try:
            memory.add(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message},
                ],
                user_id=str(user_id),
                metadata={
                    "thread_id": thread_id,
                    "source": "multi-agent-skills",
                },
            )
        except Exception as e:
            logger.warning(f"[Mem0] add failed: {e}")

    @staticmethod
    def _normalize_search_results(result: Any) -> list[str]:
        if not result:
            return []

        items = result.get("results", result) if isinstance(result, dict) else result
        if not isinstance(items, list):
            items = [items]

        memories: list[str] = []
        for item in items:
            text = ""
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = str(item.get("memory") or item.get("text") or item.get("content") or "").strip()
            else:
                text = str(getattr(item, "memory", "") or getattr(item, "text", "") or "").strip()

            if text:
                memories.append(text)

        return memories


mem0_service = Mem0Service()
