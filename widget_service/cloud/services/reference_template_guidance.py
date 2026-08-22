# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Select Design Compact reference skeletons for the generic generation path."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.logger import json_for_log, logger
from config.config import get_settings
from models.generation import TaskSpec

_MODULE = "[Reference Template Guidance]"
_PROFILE_ID = "design-compact-dsl"
_REFERENCE_TEMPLATE_2X2_FILE = "REFERENCE_TEMPLATES_2X2.md"
_REFERENCE_TEMPLATE_2X4_FILE = "REFERENCE_TEMPLATES_2X4.md"
_DEFAULT_CANDIDATE_COUNT = 3
_MAX_CANDIDATES = 3
_MAX_ASSISTANT_CHARS = 2600
_SKELETON_LOCKED_PROPS = frozenset(
    {
        "alignContent",
        "alignItems",
        "borderRadius",
        "clip",
        "flexShrink",
        "height",
        "itemMargin",
        "justifyContent",
        "layoutWeight",
        "margin",
        "padding",
        "width",
    }
)
_MARKER_USER = re.compile(r"^(?:#+\s*)?user\s*$", re.IGNORECASE)
_MARKER_ASSISTANT = re.compile(r"^(?:#+\s*)?assistant\s*$", re.IGNORECASE)
_LATIN_TOKEN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_CJK_BIGRAM = re.compile(r"[\u3400-\u9fff]{2}")


@dataclass(frozen=True)
class ReferenceTemplateExample:
    """One user/assistant template pair from the local prompt-derived library."""

    title: str
    user_payload: dict[str, Any]
    assistant_dsl: str

    @property
    def user_query(self) -> str:
        value = self.user_payload.get("userQuery")
        return value if isinstance(value, str) else ""

    @property
    def size(self) -> str:
        value = self.user_payload.get("size")
        return value if isinstance(value, str) else ""


def build_reference_template_system_prefix(
    task_spec: TaskSpec,
    *,
    profiles_root: Path | None = None,
    max_candidates: int = _DEFAULT_CANDIDATE_COUNT,
) -> str:
    """Build the reference-template block prepended before PROMPT.md/PROMPT24.md."""
    candidate_count = max(0, min(max_candidates, _MAX_CANDIDATES))
    if candidate_count == 0:
        return ""

    path = _reference_template_file(task_spec.size, profiles_root=profiles_root)
    if not path.is_file():
        logger.info(f"{_MODULE} skipped reason=examples_file_missing path={path}")
        return ""

    try:
        examples = parse_reference_template_examples(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        logger.warning(
            f"{_MODULE} skipped reason=examples_file_unreadable "
            f"path={json_for_log(str(path))} detail={json_for_log(str(exc))}"
        )
        return ""

    selected = rank_reference_template_examples(task_spec, examples)[:candidate_count]
    if not selected:
        return ""

    logger.info(
        f"{_MODULE} selected size={task_spec.size} "
        f"candidate_count={len(selected)} source_path={json_for_log(str(path))}"
    )
    has_skeleton_contract = task_spec.size in {"2x2", "2x4"}
    blocks = [
        "# 前置参考最优模板\n"
        "以下参考示例由服务端在进入通用 PROMPT 前按当前 TaskSpec 自动选择。"
        f"{task_spec.size} 候选库只包含 8 个 gold 标准样例，服务端只从这 8 个里推荐 Top 3。"
        + (
            "【骨架选择硬约束】：本次生成必须从以下 Top 3 中选择 1 个作为 selectedTemplateId，"
            "并保持该模板的组件树骨架和 lockedProps。允许填充/替换的只有 slot 内容：Text.content、"
            "Image.src/fillColor、ActionUnit.label/icon/onClick/actionInk/actionSurface、"
            "绑定 path、data 行和 root.design。"
            "不得新增布局结构、不得重排 root children、不得把 capsule/icon-round 换位置；"
            "可删除的 optional slot 仅限模板里本来就是可选的标题图标、辅助文本或 action。"
            if has_skeleton_contract
            else "它们只用于学习相近卡片的信息取舍、层级、布局骨架、动作位置和色彩方向；"
        )
        + "后续 PROMPT 正文、当前 TaskSpec、候选能力、素材和转换器约束优先级更高。"
        "不得复制示例里的旧组件、旧属性、演示事件或当前 TaskSpec 未声明字段。\n"
        "PROMPT 内置 canonical examples 只用于协议合法性，不是风格库。"
        + (
            f"本次 {task_spec.size} 输出必须先内部选择一个前置骨架，再只做 slot 填充。"
            if has_skeleton_contract
            else (
                "本次生成优先参考以下 Top 3；其余 gold few-shot 只作为标准边界，"
                "不覆盖本次前置推荐。"
            )
        )
    ]
    for rank, (score, matched, example) in enumerate(selected, start=1):
        block_lines = [
            f"## 参考模板 {rank}：{example.title}",
        ]
        if has_skeleton_contract:
            template_id = _template_id(example, rank=rank)
            skeleton_contract = _template_skeleton_contract(
                example,
                template_id=template_id,
            )
            block_lines.extend(
                [
                    "templateId=" + template_id,
                    "### skeletonContract",
                    "```json",
                    json.dumps(
                        skeleton_contract,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "```",
                ]
            )
        block_lines.extend(
            [
                "score=" + str(score),
                "matchedSignals="
                + json.dumps(matched, ensure_ascii=False, separators=(",", ":")),
                "### user",
                "```json",
                json.dumps(
                    example.user_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "```",
                "### assistant",
                "```genui",
                _truncate_assistant_dsl(example.assistant_dsl),
                "```",
            ]
        )
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks).strip()


def parse_reference_template_examples(raw: str) -> tuple[ReferenceTemplateExample, ...]:
    """Parse prompt-style `### user` / `### assistant` example pairs."""
    examples: list[ReferenceTemplateExample] = []
    state = ""
    current_title = ""
    user_lines: list[str] = []
    assistant_lines: list[str] = []

    def flush() -> None:
        if not user_lines or not assistant_lines:
            return
        user_text = "\n".join(user_lines).strip()
        assistant_text = "\n".join(assistant_lines).strip()
        if not user_text or not assistant_text:
            return
        try:
            user_payload = json.loads(_strip_code_fence(user_text))
        except json.JSONDecodeError:
            return
        if isinstance(user_payload, dict):
            examples.append(
                ReferenceTemplateExample(
                    title=current_title,
                    user_payload=user_payload,
                    assistant_dsl=_strip_code_fence(assistant_text),
                )
            )

    for line in raw.splitlines():
        marker = line.strip()
        if marker.startswith("## 示例"):
            if state == "assistant":
                flush()
                user_lines = []
                assistant_lines = []
            current_title = marker.removeprefix("## ").strip()
            state = ""
            continue
        if _MARKER_USER.fullmatch(marker):
            if state == "assistant":
                flush()
            state = "user"
            user_lines = []
            assistant_lines = []
            continue
        if _MARKER_ASSISTANT.fullmatch(marker):
            state = "assistant"
            continue
        if state == "user":
            if marker or user_lines:
                user_lines.append(line)
            continue
        if state == "assistant":
            assistant_lines.append(line)
    flush()
    return tuple(examples)


def rank_reference_template_examples(
    task_spec: TaskSpec,
    examples: tuple[ReferenceTemplateExample, ...],
) -> list[tuple[int, list[str], ReferenceTemplateExample]]:
    """Rank templates by size, user text, data fields, event calls and assets."""
    request_payload = task_spec.model_dump(mode="json", exclude_none=True)
    request_signals = _payload_signals(request_payload)
    request_terms = _text_terms(task_spec.userQuery)
    scored: list[tuple[int, int, list[str], ReferenceTemplateExample]] = []
    for index, example in enumerate(examples):
        example_signals = _payload_signals(example.user_payload)
        example_terms = _text_terms(example.user_query)
        matched_signals = sorted(request_signals & example_signals)
        matched_terms = sorted(request_terms & example_terms)
        score = 0
        score += 4 if example.size == task_spec.size else 0
        score += len(matched_terms)
        score += 2 * len(matched_signals)
        if example.user_query and task_spec.userQuery in example.user_query:
            score += 4
        elif example.user_query and example.user_query in task_spec.userQuery:
            score += 4
        matched = [*matched_signals[:8], *matched_terms[:8]]
        scored.append((score, index, matched, example))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        (score, matched, example)
        for score, _index, matched, example in scored
        if score > 0
    ]


def _reference_template_file(size: str, *, profiles_root: Path | None = None) -> Path:
    root = profiles_root or get_settings().data_root / "protocol_profiles"
    file_name = (
        _REFERENCE_TEMPLATE_2X4_FILE
        if size in {"2x4", "4x2"}
        else _REFERENCE_TEMPLATE_2X2_FILE
    )
    return root / _PROFILE_ID / file_name


def _payload_signals(payload: dict[str, Any]) -> set[str]:
    signals: set[str] = set()
    data_model = payload.get("dataModelSchema")
    if isinstance(data_model, dict):
        _collect_schema_signals(data_model, signals)
    for event in payload.get("eventCandidates", []):
        if isinstance(event, dict):
            _collect_event_signals(event, signals)
    for asset in payload.get("assetCandidates", []):
        if isinstance(asset, dict):
            src = asset.get("src")
            if isinstance(src, str) and src:
                signals.add(f"asset:{Path(src).name.casefold()}")
    return signals


def _collect_schema_signals(
    value: Any,
    signals: set[str],
    path: tuple[str, ...] = (),
) -> None:
    if isinstance(value, dict):
        if "type" in value:
            signals.add("field:" + "/".join(path).casefold())
            description = value.get("description")
            if isinstance(description, str):
                for term in tuple(_text_terms(description))[:4]:
                    signals.add(f"description:{term}")
            return
        for key, child in value.items():
            _collect_schema_signals(child, signals, (*path, str(key)))
        return
    if isinstance(value, list):
        for item in value:
            _collect_schema_signals(item, signals, path)


def _collect_event_signals(event: dict[str, Any], signals: set[str]) -> None:
    call = event.get("call")
    if isinstance(call, str):
        signals.add(f"event:{call.casefold()}")
    args = event.get("args")
    if isinstance(args, dict):
        for key in ("intentName", "bundleName", "abilityName", "uri"):
            value = args.get(key)
            if isinstance(value, str) and value:
                signals.add(f"event:{value.casefold()}")


def _text_terms(value: str) -> set[str]:
    normalized = value.casefold()
    terms = {match.group(0) for match in _LATIN_TOKEN.finditer(normalized)}
    for chunk in _CJK_RUN.findall(normalized):
        for index in range(max(0, len(chunk) - 1)):
            terms.add(chunk[index : index + 2])
    return {term for term in terms if _CJK_BIGRAM.fullmatch(term) or len(term) >= 2}


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _template_id(example: ReferenceTemplateExample, *, rank: int) -> str:
    title = example.title
    match = re.search(r"\((2x[24]-[A-Za-z0-9]+)\)", title)
    if match is not None:
        return match.group(1).casefold()
    words = [
        match.group(0).casefold()
        for match in re.finditer(r"[a-z0-9]+", title, re.IGNORECASE)
    ]
    suffix = "-".join(words[:4]) if words else f"rank-{rank}"
    return f"template-{suffix}"


def _template_skeleton_contract(
    example: ReferenceTemplateExample,
    *,
    template_id: str,
) -> dict[str, Any]:
    rows = _assistant_component_rows(example.assistant_dsl)
    components = {
        component["id"]: component
        for component in rows
    }
    root = components.get("root", {})
    return {
        "templateId": template_id,
        "selectionInstruction": (
            "选中该模板后必须保持骨架，只填 slots；不要新增、重排或改写容器 children。"
        ),
        "rootChildren": root.get("children", []),
        "containers": _container_contracts(rows),
        "fillableSlots": _fillable_slot_contracts(rows),
    }


def _assistant_component_rows(assistant_dsl: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in assistant_dsl.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("["):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            not isinstance(value, list)
            or len(value) < 3
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
            or not isinstance(value[2], dict)
            or value[0].startswith("/")
        ):
            continue
        children = value[3] if len(value) >= 4 and isinstance(value[3], list) else []
        rows.append(
            {
                "id": value[0],
                "component": value[1],
                "props": value[2],
                "children": [child for child in children if isinstance(child, str)],
            }
        )
    return rows


def _container_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for row in rows:
        children = row.get("children", [])
        if not children:
            continue
        locked_props = _locked_container_props(row.get("props", {}))
        containers.append(
            {
                "id": row["id"],
                "component": row["component"],
                "children": children,
                **({"lockedProps": locked_props} if locked_props else {}),
            }
        )
    return containers[:24]


def _locked_container_props(props: dict[str, Any]) -> dict[str, Any]:
    return {
        name: copy.deepcopy(value)
        for name, value in props.items()
        if name in _SKELETON_LOCKED_PROPS
    }


def _fillable_slot_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for row in rows:
        props = row.get("props", {})
        component_type = row.get("component")
        if row.get("id") == "root":
            slots.append(
                {
                    "id": "root",
                    "component": "Column",
                    "fillable": ["design"],
                }
            )
            continue
        if component_type == "Text":
            slots.append(
                {
                    "id": row["id"],
                    "component": "Text",
                    "fillable": ["content"],
                    "current": _slot_preview(props.get("content")),
                }
            )
            continue
        if component_type == "Image":
            slots.append(
                {
                    "id": row["id"],
                    "component": "Image",
                    "fillable": ["src", "fillColor"],
                    "current": _slot_preview(props.get("src")),
                }
            )
            continue
        if component_type == "ActionUnit":
            state = props.get("state")
            fillable = ["onClick", "actionInk", "actionSurface"]
            if state == "capsule":
                fillable.extend(["label", "icon"])
            elif state == "icon-round":
                fillable.append("icon")
            slots.append(
                {
                    "id": row["id"],
                    "component": "ActionUnit",
                    "state": state,
                    "fillable": fillable,
                }
            )
            continue
        if component_type == "Progress":
            slots.append(
                {
                    "id": row["id"],
                    "component": "Progress",
                    "fillable": ["value", "total", "color"],
                }
            )
    return slots[:32]


def _slot_preview(value: Any) -> Any:
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            return {"path": path}
        return "<object>"
    if isinstance(value, str):
        return value[:32]
    return value


def _truncate_assistant_dsl(value: str) -> str:
    if len(value) <= _MAX_ASSISTANT_CHARS:
        return value
    return value[:_MAX_ASSISTANT_CHARS].rstrip() + "\n...省略后续参考行"
