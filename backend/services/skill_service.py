from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException, UploadFile

from backend.schemas.skill import SkillCreate
from skills.auto_script_loader import load_script_tools_with_errors
from skills.registry import (
    SKILL_REGISTRY,
    inject_mcp_tools_into_registry,
    load_skill_json,
    reload_skill_registry,
)
from utils.path_tool import get_abs_path


PROTECTED_SKILLS = {"base-assistant", "base_assistant"}
MAX_ZIP_SIZE = 20 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = {
    ".md",
    ".json",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
}
SAFE_MCP_COMMANDS = {"python", "python3", "node", "npx", "uv", "uvx"}


def normalize_skill_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-_")
    return normalized


def skills_file_root() -> Path:
    return Path(get_abs_path("skills/file")).resolve()


def candidate_skill_roots() -> list[Path]:
    project_root = Path(get_abs_path(".")).resolve()
    return [
        skills_file_root(),
        (project_root / "skills").resolve(),
    ]


def _is_path_inside(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_skill_md_metadata(skill_md: Path) -> tuple[dict[str, Any], str]:
    raw = skill_md.read_text(encoding="utf-8")

    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid SKILL.md frontmatter: {e}") from e

    return meta, parts[2].strip()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _metadata_for_dir(skill_dir: Path) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise HTTPException(status_code=400, detail="SKILL.md is required")

    md_meta, _ = _read_skill_md_metadata(skill_md)
    json_meta = load_skill_json(skill_dir)
    raw_name = json_meta.get("name") or md_meta.get("name") or skill_dir.name
    name = normalize_skill_name(str(raw_name))
    description = str(json_meta.get("description") or md_meta.get("description") or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Skill name must contain letters, numbers, '-' or '_'")

    if not description:
        raise HTTPException(status_code=400, detail="Skill description is required for routing")

    return name, description, json_meta, md_meta


def _validate_files(skill_dir: Path) -> None:
    for item in skill_dir.rglob("*"):
        rel = item.relative_to(skill_dir)

        if "__pycache__" in rel.parts:
            continue

        if item.is_symlink():
            raise HTTPException(status_code=400, detail=f"Symlink is not allowed: {rel}")

        if any(part in {"..", ""} for part in rel.parts):
            raise HTTPException(status_code=400, detail=f"Unsafe path: {rel}")

        if item.is_dir():
            continue

        if item.suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Illegal file type: {rel}")

        if item.suffix.lower() == ".py":
            rel_parts = rel.parts
            if len(rel_parts) < 2 or rel_parts[0] != "scripts":
                raise HTTPException(status_code=400, detail=f"Python files must be under scripts/: {rel}")


def _validate_mcp_config(mcp_servers: dict[str, Any]) -> None:
    if not isinstance(mcp_servers, dict):
        raise HTTPException(status_code=400, detail="mcp_servers must be an object")

    for server_name, config in mcp_servers.items():
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail=f"Invalid MCP config for {server_name}")

        command = config.get("command")
        if not command:
            continue

        command_name = Path(str(command).split()[0]).name.lower()
        if command_name.endswith(".exe"):
            command_name = command_name[:-4]

        if command_name not in SAFE_MCP_COMMANDS:
            raise HTTPException(
                status_code=400,
                detail=f"Untrusted MCP command for {server_name}: {command}",
            )


def _load_preview(skill_dir: Path) -> dict[str, Any]:
    name, description, json_meta, _ = _metadata_for_dir(skill_dir)
    _validate_files(skill_dir)
    _validate_mcp_config(json_meta.get("mcp_servers", {}) or {})

    tools, errors = load_script_tools_with_errors(skill_dir)
    has_mcp = bool(json_meta.get("mcp_servers"))
    skill_json = load_skill_json(skill_dir)

    return {
        "name": name,
        "description": description,
        "tool_count": len(tools),
        "has_mcp": has_mcp,
        "enabled": bool(json_meta.get("enabled", True)),
        "degraded": bool(errors),
        "load_errors": errors,
        "skill_json": skill_json,
    }


def _ensure_skill_json(skill_dir: Path, name: str, description: str, enabled: bool = True) -> None:
    skill_json = skill_dir / "skill.json"
    data = load_skill_json(skill_dir)
    data["name"] = name
    data["description"] = description
    data.setdefault("enabled", enabled)
    _write_json(skill_json, data)


def _copy_tree_to_registry(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        raise HTTPException(status_code=409, detail="Skill already exists")

    shutil.copytree(
        source_dir,
        target_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.pyd"),
    )


async def reload_runtime() -> None:
    reload_skill_registry()
    await inject_mcp_tools_into_registry()

    try:
        from backend.services.agent_service import agent_service

        if getattr(agent_service, "_initialized", False):
            await agent_service.reload()
    except Exception as e:
        if not SKILL_REGISTRY:
            raise HTTPException(status_code=500, detail=f"Skills reloaded but agent graph rebuild failed: {e}") from e
        return


def skill_payload(skill) -> dict[str, Any]:
    canonical_name = normalize_skill_name(skill.name)

    return {
        "name": skill.name,
        "description": skill.description,
        "tool_count": len(skill.tools),
        "needs_time_context": getattr(skill, "needs_time_context", False),
        "skill_path": skill.skill_path,
        "skill_dir": skill.skill_dir,
        "has_mcp": bool(getattr(skill, "mcp_servers", {})),
        "enabled": bool(getattr(skill, "enabled", True)),
        "degraded": bool(getattr(skill, "degraded", False)),
        "load_errors": list(getattr(skill, "load_errors", [])),
        "protected": canonical_name in PROTECTED_SKILLS,
    }


def list_skills() -> list[dict[str, Any]]:
    return [skill_payload(skill) for skill in SKILL_REGISTRY.values()]


def get_skill_detail(skill_name: str) -> dict[str, Any]:
    lookup_name = normalize_skill_name(skill_name)
    skill = SKILL_REGISTRY.get(skill_name) or SKILL_REGISTRY.get(lookup_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill_dir = Path(skill.skill_dir)
    skill_md_path = skill_dir / "SKILL.md"
    skill_json_path = skill_dir / "skill.json"

    detail = skill_payload(skill)
    detail.update(
        {
            "skill_md": skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else "",
            "skill_json": load_skill_json(skill_dir) if skill_json_path.exists() else {},
            "tools": [
                {
                    "name": getattr(tool, "name", str(tool)),
                    "description": getattr(tool, "description", "") or "",
                }
                for tool in skill.tools
            ],
            "mcp_servers": getattr(skill, "mcp_servers", {}),
            "mcp_tool_allowlist": getattr(skill, "mcp_tool_allowlist", []),
        }
    )
    return detail


async def create_prompt_skill(req: SkillCreate) -> dict[str, Any]:
    skill_name = normalize_skill_name(req.name)

    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill name must contain letters, numbers, '-' or '_'")

    root = skills_file_root()
    skill_dir = (root / skill_name).resolve()

    if not _is_path_inside(root, skill_dir):
        raise HTTPException(status_code=400, detail="Invalid skill name")

    if skill_dir.exists() or skill_name in SKILL_REGISTRY:
        raise HTTPException(status_code=409, detail="Skill already exists")

    skill_dir.mkdir(parents=True, exist_ok=False)

    meta = {
        "name": skill_name,
        "description": req.description.strip(),
    }

    if req.needs_time_context:
        meta["needs_time_context"] = True

    yaml_text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    (skill_dir / "SKILL.md").write_text(
        f"---\n{yaml_text}---\n\n{req.content.strip()}\n",
        encoding="utf-8",
    )
    _ensure_skill_json(skill_dir, skill_name, req.description.strip(), enabled=True)

    await reload_runtime()

    skill = SKILL_REGISTRY.get(skill_name)
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill was created but not loaded")

    return skill_payload(skill)


def _extract_zip_to_temp(file_path: Path, temp_dir: Path) -> Path:
    with zipfile.ZipFile(file_path) as zf:
        members = zf.infolist()

        if not members:
            raise HTTPException(status_code=400, detail="Zip is empty")

        total_size = sum(member.file_size for member in members)
        if total_size > MAX_ZIP_SIZE:
            raise HTTPException(status_code=413, detail="Skill package is too large")

        for member in members:
            name = member.filename.replace("\\", "/")
            parts = Path(name).parts

            if member.is_dir():
                continue

            if Path(name).is_absolute() or ".." in parts:
                raise HTTPException(status_code=400, detail=f"Unsafe zip path: {member.filename}")

            if member.external_attr >> 28 == 0xA:
                raise HTTPException(status_code=400, detail=f"Symlink is not allowed: {member.filename}")

            if "__pycache__" in parts:
                raise HTTPException(status_code=400, detail=f"Package cannot include __pycache__: {member.filename}")

            if Path(name).suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Illegal file type: {member.filename}")

        extract_root = temp_dir / "extract"
        extract_root.mkdir(parents=True, exist_ok=False)
        zf.extractall(extract_root)

    direct_skill_md = extract_root / "SKILL.md"
    if direct_skill_md.exists():
        return extract_root

    candidates = [path.parent for path in extract_root.rglob("SKILL.md")]
    if len(candidates) != 1:
        raise HTTPException(status_code=400, detail="Zip must contain exactly one SKILL.md")

    return candidates[0]


async def _save_uploaded_zip(file: UploadFile, temp_dir: Path) -> Path:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip skill packages are supported")

    upload_path = temp_dir / "upload.zip"
    size = 0

    with upload_path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break

            size += len(chunk)
            if size > MAX_ZIP_SIZE:
                raise HTTPException(status_code=413, detail="Skill package is too large")

            out.write(chunk)

    return upload_path


async def preview_skill_zip(file: UploadFile) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="skill_preview_") as temp_name:
        temp_dir = Path(temp_name)
        upload_path = await _save_uploaded_zip(file, temp_dir)
        source_dir = _extract_zip_to_temp(upload_path, temp_dir)
        preview = _load_preview(source_dir)

        return {
            "preview": preview
        }


async def import_skill_zip(file: UploadFile) -> dict[str, Any]:
    root = skills_file_root()
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="skill_import_") as temp_name:
        temp_dir = Path(temp_name)
        upload_path = await _save_uploaded_zip(file, temp_dir)
        source_dir = _extract_zip_to_temp(upload_path, temp_dir)
        preview = _load_preview(source_dir)
        target_dir = (root / preview["name"]).resolve()

        if not _is_path_inside(root, target_dir):
            raise HTTPException(status_code=400, detail="Invalid skill name")

        if target_dir.exists() or preview["name"] in SKILL_REGISTRY:
            raise HTTPException(status_code=409, detail="Skill already exists")

        _copy_tree_to_registry(source_dir, target_dir)
        _ensure_skill_json(target_dir, preview["name"], preview["description"], enabled=preview["enabled"])

    await reload_runtime()

    skill = SKILL_REGISTRY.get(preview["name"])
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill was imported but not loaded")

    return {
        "preview": preview,
        "skill": skill_payload(skill),
    }


def _resolve_candidate_source(source: str) -> Path:
    raw = source.strip().replace("\\", "/")

    if not raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
        raise HTTPException(status_code=400, detail="Source must be a safe relative path or directory name")

    project_root = Path(get_abs_path(".")).resolve()
    direct = (project_root / raw).resolve()
    if _is_path_inside(project_root, direct) and direct.is_dir() and (direct / "SKILL.md").exists():
        return direct

    for root in candidate_skill_roots():
        candidate = (root / raw).resolve()
        if _is_path_inside(root, candidate) and candidate.is_dir() and (candidate / "SKILL.md").exists():
            return candidate

    raise HTTPException(status_code=404, detail="Candidate skill directory not found")


async def import_skill_directory(source: str) -> dict[str, Any]:
    source_dir = _resolve_candidate_source(source)
    preview = _load_preview(source_dir)
    root = skills_file_root()
    target_dir = (root / preview["name"]).resolve()

    if not _is_path_inside(root, target_dir):
        raise HTTPException(status_code=400, detail="Invalid skill name")

    if target_dir.exists() and source_dir.resolve() != target_dir:
        raise HTTPException(status_code=409, detail="Skill already exists")

    if source_dir.resolve() != target_dir:
        _copy_tree_to_registry(source_dir, target_dir)
        _ensure_skill_json(target_dir, preview["name"], preview["description"], enabled=preview["enabled"])

    await reload_runtime()

    skill = SKILL_REGISTRY.get(preview["name"])
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill was imported but not loaded")

    return {
        "preview": preview,
        "skill": skill_payload(skill),
    }


async def set_skill_enabled(skill_name: str, enabled: bool) -> dict[str, Any]:
    lookup_name = normalize_skill_name(skill_name)
    skill = SKILL_REGISTRY.get(skill_name) or SKILL_REGISTRY.get(lookup_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    canonical_name = normalize_skill_name(skill.name)
    if not enabled and canonical_name in PROTECTED_SKILLS:
        raise HTTPException(status_code=400, detail="Protected skill cannot be disabled")

    skill_dir = Path(skill.skill_dir)
    data = load_skill_json(skill_dir)
    data["name"] = skill.name
    data["description"] = skill.description
    data["enabled"] = enabled
    _write_json(skill_dir / "skill.json", data)

    await reload_runtime()

    updated = SKILL_REGISTRY.get(skill_name) or SKILL_REGISTRY.get(lookup_name) or SKILL_REGISTRY.get(data["name"])
    if updated is None:
        raise HTTPException(status_code=500, detail="Skill updated but not loaded")

    return skill_payload(updated)


async def delete_skill(skill_name: str) -> None:
    lookup_name = normalize_skill_name(skill_name)
    skill = SKILL_REGISTRY.get(skill_name) or SKILL_REGISTRY.get(lookup_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    canonical_name = normalize_skill_name(skill.name)
    if canonical_name in PROTECTED_SKILLS:
        raise HTTPException(status_code=400, detail="Protected skill cannot be deleted")

    root = skills_file_root()
    skill_dir = Path(skill.skill_dir).resolve()

    if not _is_path_inside(root, skill_dir):
        raise HTTPException(status_code=400, detail="Only file skills can be deleted")

    shutil.rmtree(skill_dir)
    await reload_runtime()
