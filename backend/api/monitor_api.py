import ast
import json
import re
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.deps import require_admin
from backend.repositories.monitor_repository import (
    get_agent_run,
    get_monitor_summary,
    list_agent_run_steps,
    list_agent_runs,
    list_agent_tool_calls,
)
from backend.repositories.user_repository import get_user_by_id
from backend.schemas.user import CurrentUser


router = APIRouter()


def _latency_ms(started_at, finished_at) -> int | None:
    if not started_at or not finished_at:
        return None
    return int((finished_at - started_at).total_seconds() * 1000)


def _parse_legacy_message_repr(value: str) -> Any:
    match = re.search(
        r"content=(?P<quote>['\"])(?P<content>[\s\S]*?)(?P=quote)(?=\s+(?:additional_kwargs|response_metadata|id|tool_calls|invalid_tool_calls|name|tool_call_id)=|\)|$)",
        value,
    )
    if not match:
        return None

    quoted = f"{match.group('quote')}{match.group('content')}{match.group('quote')}"
    try:
        content = ast.literal_eval(quoted)
    except Exception:
        content = match.group("content").replace("\\n", "\n").replace('\\"', '"')

    try:
        content = json.loads(content)
    except Exception:
        pass

    message = {
        "type": "ToolMessage"
        if value.lstrip().startswith("ToolMessage") or "tool_call_id=" in value
        else "LangChainMessage",
        "content": content,
    }

    for field in ("name", "tool_call_id"):
        field_match = re.search(
            rf"{field}=(?P<quote>['\"])(?P<value>[\s\S]*?)(?P=quote)",
            value,
        )
        if field_match:
            message[field] = field_match.group("value")

    return message


def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    try:
        parsed = json.loads(value)
    except Exception:
        return _parse_legacy_message_repr(value) or value

    if isinstance(parsed, str):
        return _parse_legacy_message_repr(parsed) or parsed
    return parsed


def _parse_json_like_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text or text[0] not in "{[":
        return value

    try:
        return json.loads(text)
    except Exception:
        return value


def _message_content(value: Any) -> Any:
    payload = _parse_json(value)

    if isinstance(payload, dict) and "content" in payload:
        return _parse_json_like_text(payload.get("content"))

    return payload


def _normalize_task(task: Any) -> dict | None:
    if not isinstance(task, dict):
        return None

    skill = task.get("skill")
    sub_task = task.get("sub_task") or task.get("task") or task.get("description")
    if not skill and not sub_task:
        return None

    normalized = dict(task)
    if skill:
        normalized["skill"] = skill
    if sub_task:
        normalized["sub_task"] = sub_task
    return normalized


def _extract_tasks_from_payload(value: Any) -> list[dict]:
    payload = _parse_json(value)
    candidates: list[Any] = []

    if isinstance(payload, list):
        candidates.extend(payload)

    if isinstance(payload, dict):
        for key in ("tasks", "plan"):
            if isinstance(payload.get(key), list):
                candidates.extend(payload[key])

        if "content" in payload:
            content = _message_content(payload)
            if isinstance(content, dict):
                for key in ("tasks", "plan"):
                    if isinstance(content.get(key), list):
                        candidates.extend(content[key])
            elif isinstance(content, list):
                candidates.extend(content)

    tasks = [_normalize_task(item) for item in candidates]
    result: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for task in tasks:
        if not task:
            continue

        identity = (
            str(task.get("skill") or ""),
            str(task.get("sub_task") or ""),
        )
        if identity in seen:
            continue

        seen.add(identity)
        result.append(task)

    return result


def _first_tasks_from_steps(steps) -> list[dict]:
    for step in steps:
        if step.node_name != "router":
            continue

        tasks = _extract_tasks_from_payload(step.output_json)
        if tasks:
            return tasks

    return []


def _infer_main_skill(run, steps) -> str | None:
    if run.main_skill:
        return run.main_skill

    tasks = _first_tasks_from_steps(steps)
    skills = [
        task.get("skill")
        for task in tasks
        if task.get("skill")
    ]
    if skills:
        return ",".join(dict.fromkeys(skills))

    for step in steps:
        payload = _parse_json(step.input_json) or _parse_json(step.output_json)
        if not isinstance(payload, dict):
            continue

        task_info = payload.get("task_info")
        if isinstance(task_info, dict) and task_info.get("skill"):
            return str(task_info["skill"])

        if payload.get("skill"):
            return str(payload["skill"])

    return None


def _user_label(db: Session, user_id: int) -> tuple[str | None, str]:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None, f"用户 {user_id}"

    return user.username, user.nickname or user.username


def _run_payload(run, db: Session, steps=None) -> dict:
    steps = steps if steps is not None else list_agent_run_steps(db=db, run_id=run.run_id)
    username, user_label = _user_label(db, run.user_id)

    return {
        "run_id": run.run_id,
        "thread_id": run.thread_id,
        "user_id": run.user_id,
        "username": username,
        "user_label": user_label,
        "message_id": run.message_id,
        "input": run.input,
        "output": run.output,
        "status": run.status,
        "main_skill": _infer_main_skill(run, steps),
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "latency_ms": _latency_ms(run.started_at, run.finished_at),
    }


def _step_payload(step) -> dict:
    return {
        "id": step.id,
        "run_id": step.run_id,
        "step_index": step.step_index,
        "node_name": step.node_name,
        "event_type": step.event_type,
        "input_json": step.input_json,
        "output_json": step.output_json,
        "error": step.error,
        "created_at": step.created_at.isoformat(),
    }


def _tool_call_payload(tool_call) -> dict:
    return {
        "id": tool_call.id,
        "run_id": tool_call.run_id,
        "step_index": tool_call.step_index,
        "tool_name": tool_call.tool_name,
        "skill": tool_call.skill,
        "tool_input_json": tool_call.tool_input_json,
        "tool_output_json": tool_call.tool_output_json,
        "status": tool_call.status,
        "latency_ms": tool_call.latency_ms,
        "created_at": tool_call.created_at.isoformat(),
    }


def _worker_output(payload: Any) -> Any:
    payload = _parse_json(payload)
    if not isinstance(payload, dict):
        return payload

    messages = payload.get("messages")
    if isinstance(messages, list) and messages:
        for message in reversed(messages):
            message_payload = _parse_json(message)
            if isinstance(message_payload, dict):
                message_type = str(message_payload.get("type") or "")
                if message_type == "ToolMessage" or message_payload.get("tool_call_id"):
                    continue
                content = _message_content(message_payload)
            else:
                content = _message_content(message)
            if content:
                return content

    return payload


def _dedupe_tool_calls(tool_calls) -> list:
    priority = {
        "running": 0,
        "observed": 1,
        "failed": 2,
        "success": 3,
    }
    result: list[Any] = []
    skill_by_identity: dict[tuple[str, str, str], str] = {}

    def score(item) -> tuple[int, int, int]:
        return (
            priority.get(item.status, 0),
            1 if item.tool_input_json else 0,
            1 if item.tool_output_json else 0,
        )

    def parsed_input(item) -> Any:
        return _parse_json(item.tool_input_json)

    def parsed_output(item) -> Any:
        return _parse_json(item.tool_output_json)

    def text_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def empty_value(value: Any) -> bool:
        return value in (None, "", [], {})

    def same_tool(left, right) -> bool:
        if left.tool_name != right.tool_name:
            return False

        left_skill = left.skill or getattr(left, "_monitor_skill", None)
        right_skill = right.skill or getattr(right, "_monitor_skill", None)
        if left_skill and right_skill and left_skill != right_skill:
            return False

        left_input = parsed_input(left)
        right_input = parsed_input(right)
        if left_input and right_input and left_input == right_input:
            return True

        left_output = text_value(parsed_output(left))
        right_output = text_value(parsed_output(right))
        if (
            (left_input == right_input or empty_value(left_input) or empty_value(right_input))
            and (left_output == right_output or not left_output or not right_output)
        ):
            return True

        if left_output and right_output:
            short, long = sorted((left_output, right_output), key=len)
            if short and short in long:
                return True
            return SequenceMatcher(None, left_output, right_output).ratio() >= 0.92

        return False

    def identity(item) -> tuple[str, str, str]:
        return (
            str(item.tool_name),
            text_value(parsed_input(item)),
            "",
        )

    for tool_call in tool_calls:
        if tool_call.skill:
            skill_by_identity[identity(tool_call)] = tool_call.skill

    for tool_call in tool_calls:
        match_index = next(
            (
                index
                for index, current in enumerate(result)
                if same_tool(current, tool_call)
            ),
            None,
        )
        if match_index is None:
            result.append(tool_call)
            continue

        current = result[match_index]
        if score(tool_call) > score(current):
            result[match_index] = tool_call

    for tool_call in result:
        if not tool_call.skill:
            tool_call._monitor_skill = skill_by_identity.get(identity(tool_call))

    return sorted(
        result,
        key=lambda item: (item.step_index, item.id),
    )


def _tool_trace_payload(tool_call) -> dict:
    skill = tool_call.skill or getattr(tool_call, "_monitor_skill", None)
    return {
        "id": tool_call.id,
        "step_index": tool_call.step_index,
        "tool_name": tool_call.tool_name,
        "skill": skill,
        "status": tool_call.status,
        "latency_ms": tool_call.latency_ms,
        "input": _parse_json(tool_call.tool_input_json),
        "output": _message_content(tool_call.tool_output_json),
    }


def _build_trace(run, steps, tool_calls) -> list[dict]:
    trace: list[dict] = [
        {
            "id": f"{run.run_id}:input",
            "type": "user_input",
            "title": "用户输入",
            "input": run.input,
        }
    ]

    tasks = _first_tasks_from_steps(steps)
    if tasks:
        trace.append(
            {
                "id": f"{run.run_id}:router",
                "type": "router",
                "title": "Router 分配子 Agent",
                "output": {
                    "tasks": tasks,
                },
            }
        )

    worker_items: list[dict] = []
    open_workers: list[dict] = []

    for step in steps:
        if step.event_type == "worker_start":
            payload = _parse_json(step.input_json) or {}
            task_info = payload.get("task_info") if isinstance(payload, dict) else {}
            worker = {
                "id": f"{run.run_id}:worker:{step.id}",
                "type": "worker",
                "title": f"子 Agent: {task_info.get('skill', 'unknown') if isinstance(task_info, dict) else 'unknown'}",
                "skill": task_info.get("skill") if isinstance(task_info, dict) else None,
                "status": "running",
                "step_index": step.step_index,
                "end_step_index": None,
                "input": task_info,
                "output": None,
                "tools": [],
                "error": None,
            }
            worker_items.append(worker)
            open_workers.append(worker)

        elif step.event_type in {"worker_end", "worker_error"}:
            payload = _parse_json(step.output_json) or {}
            skill = payload.get("skill") if isinstance(payload, dict) else None
            worker = None
            for item in reversed(open_workers):
                if skill is None or item.get("skill") == skill:
                    worker = item
                    break

            if worker is None:
                worker = {
                    "id": f"{run.run_id}:worker:{step.id}",
                    "type": "worker",
                    "title": f"子 Agent: {skill or 'unknown'}",
                    "skill": skill,
                    "step_index": step.step_index,
                    "input": None,
                    "tools": [],
                }
                worker_items.append(worker)

            worker["status"] = "failed" if step.event_type == "worker_error" else "success"
            worker["end_step_index"] = step.step_index
            worker["output"] = _worker_output(step.output_json)
            worker["error"] = step.error
            if worker in open_workers:
                open_workers.remove(worker)

    deduped_tools = _dedupe_tool_calls(tool_calls)
    ordered_workers = sorted(
        (
            worker
            for worker in worker_items
            if worker.get("step_index") is not None
        ),
        key=lambda item: (item.get("step_index") or 0, item.get("id") or ""),
    )

    for tool_call in deduped_tools:
        attached = False
        tool_skill = tool_call.skill or getattr(tool_call, "_monitor_skill", None)
        if tool_skill:
            for worker in ordered_workers:
                if worker.get("skill") == tool_skill:
                    worker["tools"].append(_tool_trace_payload(tool_call))
                    attached = True
                    break
        else:
            for worker in reversed(ordered_workers):
                start = worker.get("step_index") or 0
                if start <= tool_call.step_index:
                    worker["tools"].append(_tool_trace_payload(tool_call))
                    attached = True
                    break

        if not attached:
            for worker in ordered_workers:
                known_tool_names = {
                    item.get("tool_name")
                    for item in worker.get("tools", [])
                }
                if tool_call.tool_name in known_tool_names:
                    worker["tools"].append(_tool_trace_payload(tool_call))
                    attached = True
                    break

        if not attached:
            for worker in ordered_workers:
                worker_input = worker.get("input")
                if not isinstance(worker_input, dict):
                    continue
                skill = worker_input.get("skill")
                if skill and skill == tool_skill:
                    worker["tools"].append(_tool_trace_payload(tool_call))
                    attached = True
                    break

        if not attached and not tool_skill:
            for worker in reversed(ordered_workers):
                start = worker.get("step_index") or 0
                end = worker.get("end_step_index")
                if start <= tool_call.step_index and (end is None or tool_call.step_index <= end):
                    worker["tools"].append(_tool_trace_payload(tool_call))
                    attached = True
                    break

        if not attached and ordered_workers:
            ordered_workers[0]["tools"].append(_tool_trace_payload(tool_call))

    for worker in worker_items:
        worker["tools"] = sorted(
            worker.get("tools", []),
            key=lambda item: (item.get("step_index") or 0, item.get("id") or 0),
        )

    trace.extend(worker_items)

    if run.output:
        trace.append(
            {
                "id": f"{run.run_id}:summarizer",
                "type": "summarizer",
                "title": "Summarizer 输出",
                "output": run.output,
            }
        )

    return trace


@router.get("/summary")
def summary(
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_monitor_summary(db)


@router.get("/runs")
def runs(
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "runs": [
            _run_payload(run, db=db)
            for run in list_agent_runs(db=db, limit=limit)
        ]
    }


@router.get("/runs/{run_id}")
def run_detail(
    run_id: str,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    run = get_agent_run(db=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_agent_run_steps(db=db, run_id=run_id)
    tool_calls = list_agent_tool_calls(db=db, run_id=run_id)

    return {
        "run": _run_payload(run, db=db, steps=steps),
        "steps": [_step_payload(step) for step in steps],
        "tool_calls": [_tool_call_payload(tool_call) for tool_call in tool_calls],
        "trace": _build_trace(run, steps, tool_calls),
    }
