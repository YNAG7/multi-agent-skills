
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
    User,
    UserMemory,
)


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_monitor_tool_skill_column()


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
