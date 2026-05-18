from __future__ import annotations

from skills.skills_tools import get_skill


def compose_system_prompt(main_skill: str, aux_skills: list[str]) -> str:
    parts: list[str] = []

    # ① base_assistant 永远全量加载
    base_text = get_skill("base_assistant").load_text().strip()
    parts.append(base_text)

    # ② 主 skill 全量加载
    main_text = get_skill(main_skill).load_text().strip()
    parts.append(main_text)

    # ③ 辅助 skills 默认只加载运行摘要，避免 prompt 太乱
    for name in aux_skills:
        if name in {"base_assistant", main_skill}:
            continue

        summary = get_skill(name).load_runtime_summary()
        parts.append(f"## Auxiliary Skill: {name}\n{summary}")

    # ④ 最后拼成一个 system prompt
    return "\n\n".join(part for part in parts if part)