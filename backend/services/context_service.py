from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.repositories.chat_repository import (
    count_messages,
    get_thread_summary,
    list_messages_for_compression,
    list_recent_messages,
    upsert_thread_summary,
)
from backend.services.mem0_service import mem0_service
from model.factory import smart_chat_model
from utils.logger_handler import logger


def _format_messages(messages) -> str:
    lines: list[str] = []
    for item in messages:
        role = "用户" if item.role == "user" else "助手"
        lines.append(f"{role}: {item.content}")
    return "\n".join(lines)


def build_agent_context(
    db: Session,
    user_id: int,
    thread_id: str,
    current_message: str,
) -> str:
    recent_limit = max(settings.MEMORY_RECENT_TURNS * 2, 2)
    recent_messages = list_recent_messages(
        db=db,
        user_id=user_id,
        thread_id=thread_id,
        limit=recent_limit,
    )
    summary_item = get_thread_summary(db=db, user_id=user_id, thread_id=thread_id)
    long_term_memories = mem0_service.search(
        user_id=user_id,
        query=current_message,
        limit=settings.MEMORY_TOP_K,
    )

    sections: list[str] = []

    if long_term_memories:
        sections.append(
            "[长期记忆]\n"
            + "\n".join(f"- {memory}" for memory in long_term_memories)
        )

    if summary_item and summary_item.summary.strip():
        sections.append(f"[当前会话摘要]\n{summary_item.summary.strip()}")

    if recent_messages:
        sections.append(f"[最近对话]\n{_format_messages(recent_messages)}")

    sections.append(f"[当前用户问题]\n{current_message}")

    return "\n\n".join(sections)


async def compress_thread_if_needed(
    db: Session,
    user_id: int,
    thread_id: str,
) -> None:
    recent_limit = max(settings.MEMORY_RECENT_TURNS * 2, 2)
    threshold = max(settings.MEMORY_COMPRESS_THRESHOLD * 2, recent_limit + 2)
    total_messages = count_messages(db=db, user_id=user_id, thread_id=thread_id)

    if total_messages <= threshold:
        return

    recent_messages = list_recent_messages(
        db=db,
        user_id=user_id,
        thread_id=thread_id,
        limit=recent_limit,
    )
    if not recent_messages:
        return

    before_id = recent_messages[0].id - 1
    summary_item = get_thread_summary(db=db, user_id=user_id, thread_id=thread_id)
    after_id = summary_item.last_compressed_message_id if summary_item else 0

    if before_id <= after_id:
        return

    old_messages = list_messages_for_compression(
        db=db,
        user_id=user_id,
        thread_id=thread_id,
        after_id=after_id,
        before_id=before_id,
    )
    if not old_messages:
        return

    previous_summary = summary_item.summary if summary_item else ""
    prompt = (
        "请把以下会话历史压缩成一份简洁、准确、可继续对话使用的中文摘要。\n"
        "要求：\n"
        "1. 保留用户目标、偏好、已经做过的决定、重要文件/模块、未完成事项。\n"
        "2. 删除寒暄和重复内容。\n"
        "3. 不要编造没有出现的信息。\n"
        "4. 用项目协作备忘录风格输出。\n\n"
        f"[已有摘要]\n{previous_summary or '暂无'}\n\n"
        f"[需要合并的旧消息]\n{_format_messages(old_messages)}"
    )

    try:
        response = await smart_chat_model.ainvoke(prompt)
        summary = getattr(response, "content", str(response)).strip()
    except Exception as e:
        logger.warning(f"[Context] compression failed: {e}")
        return

    if not summary:
        return

    upsert_thread_summary(
        db=db,
        user_id=user_id,
        thread_id=thread_id,
        summary=summary,
        last_compressed_message_id=before_id,
    )
