
from sqlalchemy import inspect, text

from backend.db.database import Base, engine

# 关键：必须导入 models，SQLAlchemy 才知道有哪些表
from backend.models import (
    AgentRun,
    AgentRunStep,
    AgentToolCall,
    ChatMessage,
    ChatSession,
    ChatThreadSummary,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeParentChunk,
    User,
    UserMemory,
)


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_monitor_tool_skill_column()
    _ensure_knowledge_parent_schema()


def _ensure_monitor_tool_skill_column():
    inspector = inspect(engine)
    try:
        column_names = {column["name"] for column in inspector.get_columns("agent_tool_calls")}
    except Exception:
        return

    with engine.begin() as conn:
        if "skill" not in column_names:
            conn.execute(text("ALTER TABLE agent_tool_calls ADD COLUMN skill VARCHAR(128)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_tool_calls_skill ON agent_tool_calls (skill)"))


def _ensure_knowledge_parent_schema():
    inspector = inspect(engine)
    try:
        table_names = set(inspector.get_table_names())
    except Exception:
        return

    if "knowledge_chunks" not in table_names:
        return

    try:
        column_names = {column["name"] for column in inspector.get_columns("knowledge_chunks")}
    except Exception:
        return

    with engine.begin() as conn:
        if "parent_id" not in column_names:
            conn.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN parent_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_parent_id ON knowledge_chunks (parent_id)"))
