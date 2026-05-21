from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models import AgentRun, AgentRunStep, AgentToolCall


def _parse_json_text(value: str) -> Any:
    text = value.strip()
    if not text or text[0] not in "{[":
        return value

    try:
        return json.loads(text)
    except Exception:
        return value


def _message_payload(message: Any, depth: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": message.__class__.__name__,
    }

    content = getattr(message, "content", None)
    if content is not None:
        payload["content"] = _json_safe(content, depth + 1)

    for key in (
        "name",
        "id",
        "tool_call_id",
        "additional_kwargs",
        "response_metadata",
        "tool_calls",
        "invalid_tool_calls",
        "usage_metadata",
    ):
        value = getattr(message, key, None)
        if value:
            payload[key] = _json_safe(value, depth + 1)

    return payload


def _json_safe(data: Any, depth: int = 0) -> Any:
    if depth > 8:
        return str(data)

    if data is None or isinstance(data, (bool, int, float)):
        return data

    if isinstance(data, str):
        return _parse_json_text(data)

    if isinstance(data, dict):
        return {
            str(key): _json_safe(value, depth + 1)
            for key, value in data.items()
        }

    if isinstance(data, (list, tuple, set)):
        return [_json_safe(item, depth + 1) for item in data]

    if hasattr(data, "content") or hasattr(data, "tool_calls"):
        return _message_payload(data, depth)

    return str(data)


def _json_dumps(data: Any) -> str | None:
    if data is None:
        return None

    try:
        return json.dumps(_json_safe(data), ensure_ascii=False)
    except Exception:
        return json.dumps(str(data), ensure_ascii=False)


def create_agent_run(
    db: Session,
    run_id: str,
    thread_id: str,
    user_id: int,
    input_text: str,
    message_id: int | None = None,
) -> AgentRun:
    item = AgentRun(
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        message_id=message_id,
        input=input_text,
        status="running",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def finish_agent_run(
    db: Session,
    run_id: str,
    output: str | None,
    status: str,
    main_skill: str | None = None,
) -> AgentRun | None:
    item = db.get(AgentRun, run_id)
    if item is None:
        return None

    item.output = output
    item.status = status
    if main_skill is not None:
        item.main_skill = main_skill
    item.finished_at = datetime.now()
    db.commit()
    db.refresh(item)
    return item


def update_agent_run_main_skill(
    db: Session,
    run_id: str,
    main_skill: str | None,
) -> AgentRun | None:
    if not main_skill:
        return None

    item = db.get(AgentRun, run_id)
    if item is None:
        return None

    item.main_skill = main_skill
    db.commit()
    db.refresh(item)
    return item


def next_step_index(db: Session, run_id: str) -> int:
    current = (
        db.query(AgentRunStep.step_index)
        .filter(AgentRunStep.run_id == run_id)
        .order_by(AgentRunStep.step_index.desc())
        .limit(1)
        .scalar()
    )
    return int(current or 0) + 1


def create_agent_run_step(
    db: Session,
    run_id: str,
    step_index: int,
    node_name: str | None,
    event_type: str,
    input_data: Any = None,
    output_data: Any = None,
    error: str | None = None,
) -> AgentRunStep:
    item = AgentRunStep(
        run_id=run_id,
        step_index=step_index,
        node_name=node_name,
        event_type=event_type,
        input_json=_json_dumps(input_data),
        output_json=_json_dumps(output_data),
        error=error,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_tool_call(
    db: Session,
    run_id: str,
    step_index: int,
    tool_name: str,
    tool_input: Any = None,
    status: str = "running",
    skill: str | None = None,
) -> AgentToolCall:
    item = AgentToolCall(
        run_id=run_id,
        step_index=step_index,
        tool_name=tool_name,
        skill=skill,
        tool_input_json=_json_dumps(tool_input),
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def finish_tool_call(
    db: Session,
    tool_call_id: int,
    tool_output: Any = None,
    status: str = "success",
    latency_ms: int | None = None,
) -> AgentToolCall | None:
    item = db.get(AgentToolCall, tool_call_id)
    if item is None:
        return None

    item.tool_output_json = _json_dumps(tool_output)
    item.status = status
    item.latency_ms = latency_ms
    db.commit()
    db.refresh(item)
    return item


def list_agent_runs(
    db: Session,
    user_id: int | None = None,
    limit: int = 50,
) -> list[AgentRun]:
    query = db.query(AgentRun)
    if user_id is not None:
        query = query.filter(AgentRun.user_id == user_id)

    return query.order_by(AgentRun.started_at.desc()).limit(limit).all()


def get_agent_run(
    db: Session,
    run_id: str,
    user_id: int | None = None,
) -> AgentRun | None:
    query = db.query(AgentRun).filter(AgentRun.run_id == run_id)
    if user_id is not None:
        query = query.filter(AgentRun.user_id == user_id)

    return query.first()


def list_agent_run_steps(db: Session, run_id: str) -> list[AgentRunStep]:
    return (
        db.query(AgentRunStep)
        .filter(AgentRunStep.run_id == run_id)
        .order_by(AgentRunStep.step_index.asc(), AgentRunStep.id.asc())
        .all()
    )


def list_agent_tool_calls(db: Session, run_id: str) -> list[AgentToolCall]:
    return (
        db.query(AgentToolCall)
        .filter(AgentToolCall.run_id == run_id)
        .order_by(AgentToolCall.step_index.asc(), AgentToolCall.id.asc())
        .all()
    )


def get_monitor_summary(db: Session, user_id: int | None = None) -> dict[str, Any]:
    base_query = db.query(AgentRun)
    if user_id is not None:
        base_query = base_query.filter(AgentRun.user_id == user_id)

    total_runs = base_query.count()
    success_runs = base_query.filter(AgentRun.status == "success").count()
    failed_runs = base_query.filter(AgentRun.status == "failed").count()
    finished_runs = base_query.filter(AgentRun.finished_at.isnot(None)).all()
    latencies = [
        int((run.finished_at - run.started_at).total_seconds() * 1000)
        for run in finished_runs
        if run.finished_at and run.started_at
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return {
        "total_runs": total_runs,
        "success_runs": success_runs,
        "failed_runs": failed_runs,
        "running_runs": max(total_runs - success_runs - failed_runs, 0),
        "success_rate": success_runs / total_runs if total_runs else 0,
        "avg_latency_ms": int(avg_latency),
    }
