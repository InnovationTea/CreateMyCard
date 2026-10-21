"""独立编辑提示词加载与组装；不加载任何创建提示词。"""

import json
from pathlib import Path
from typing import Literal

from services.single_step_edit import source_digest
from services.widget_edit_contract import EditIntent, edit_contract

PROMPT_DIR = Path(__file__).resolve().parents[1] / "data/protocol_profiles/semantic-widget-edit"
_COMMON_FILES = ("protocol.md", "design.md", "examples.md")


def _read_prompt(filename: str) -> str:
    path = PROMPT_DIR / filename
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"编辑提示词读取失败：{filename}") from exc
    if not content:
        raise ValueError(f"编辑提示词不能为空：{filename}")
    return content


def _system_prompt(stage: Literal["intent", "execute"]) -> str:
    parts = [_read_prompt(f"{stage}.md")]
    for filename in _COMMON_FILES:
        parts.append(_read_prompt(filename))
    return "\n\n".join(parts)


def intent_prompt(original: str, query: str, source_size: str,
                  explicit_size: str | None, runtime_changes: dict | None = None,
                  ) -> list[dict[str, str]]:
    payload = {
        "previousGenui": original, "editInstruction": query, "sourceSize": source_size,
        "explicitTargetSize": explicit_size, "outputSchema": EditIntent.model_json_schema(),
        "runtimeChanges": runtime_changes or {}, "editContract": edit_contract(),
    }
    return [
        {"role": "system", "content": _system_prompt("intent")},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def execution_prompt(original: str, query: str, intent: EditIntent) -> list[dict[str, str]]:
    payload = {
        "previousGenui": original, "sourceDigest": source_digest(original),
        "editInstruction": query, "acceptedIntent": intent.model_dump(mode="json"),
        "editContract": edit_contract(),
    }
    return [
        {"role": "system", "content": _system_prompt("execute")},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def repair_feedback(output: str, errors: list[str], stage: str) -> list[dict[str, str]]:
    feedback = {"errors": errors, "repairStage": stage, "instruction": _read_prompt("repair.md")}
    return [
        {"role": "assistant", "content": output},
        {"role": "user", "content": json.dumps(feedback, ensure_ascii=False)},
    ]
