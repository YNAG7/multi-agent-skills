import random
import threading
import time
from typing import Any

from langchain_core.tools import tool

from utils.logger_handler import logger


user_ids = [
    "1001",
    "1002",
    "1003",
    "1004",
    "1005",
    "1006",
    "1007",
    "1008",
    "1009",
    "1010",
]

month_arr = [
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
]

_rag: Any = None
_rag_error: str | None = None
_rag_error_at: float | None = None
_rag_lock = threading.Lock()
_RAG_RETRY_SECONDS = 30


def initialize_rag(force: bool = False, warmup: bool = True) -> Any:
    """
    Build and optionally warm the shared RAG service.

    Startup calls this once so the first user query does not pay model/vector
    initialization cost. Tool calls still use it as a lazy fallback.
    """
    global _rag, _rag_error, _rag_error_at

    with _rag_lock:
        if _rag is not None and not force:
            return _rag

        if _rag_error is not None and not force:
            retry_at = (_rag_error_at or 0) + _RAG_RETRY_SECONDS
            if time.monotonic() < retry_at:
                raise RuntimeError(_rag_error)
            force = True

        if force:
            _rag = None
            _rag_error = None
            _rag_error_at = None

        try:
            from rag.rag_service import RagSummarizeService

            service = RagSummarizeService()
            if warmup:
                service.warmup()

            _rag = service
            _rag_error = None
            _rag_error_at = None
            logger.info("[RAG] service initialized")
            return _rag
        except Exception as e:
            _rag_error = str(e)
            _rag_error_at = time.monotonic()
            logger.error(f"[RAG] service initialization failed: {e}", exc_info=True)
            raise


def _get_rag() -> Any:
    return initialize_rag()


def get_initialized_rag() -> Any | None:
    return _rag


@tool(description="Search the local vector knowledge base and return reference material.")
def rag_summarize(query: str) -> str:
    try:
        return _get_rag().rag_summarize(query)
    except Exception as e:
        return f"Knowledge base search is temporarily unavailable: {e}"


@tool(description="Get weather for the specified city as a plain text message.")
def get_weather(city: str) -> str:
    return (
        f"{city} weather: sunny, temperature 26 C, humidity 50%, "
        "south wind level 1, AQI 21, very low rainfall probability in recent hours."
    )


@tool(description="Get the user's city name as a plain string.")
def get_user_location() -> str:
    return random.choice(["Shenzhen", "Hefei", "Hangzhou"])


@tool(description="Get the user's ID as a plain string.")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="Get the current month as a plain string.")
def get_current_month() -> str:
    return random.choice(month_arr)


COMMON_TOOL_EXPORTS = [
    get_current_month,
    get_user_id,
    get_user_location,
    get_weather,
    rag_summarize,
]
