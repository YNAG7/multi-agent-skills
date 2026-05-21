from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    thread_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
    )

    message_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    input: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="running",
        nullable=False,
        index=True,
    )

    main_skill: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    node_name: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
    )

    input_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    output_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    tool_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )

    skill: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
    )

    tool_input_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tool_output_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="running",
        nullable=False,
        index=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
    )
