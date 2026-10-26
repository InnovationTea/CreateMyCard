"""后置主题候选的原融合规则门禁；不负责布局或颜色展开。"""

import hashlib
import re

from models.generation import TaskSpec
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_layout_runtime import match_compact_layout
from services.compact_plan import _compact_visible_state
from services.post_layout_theme_registry import load_theme_registry
from services.prompt_builder import PromptBuilder


def default_palette_family(task: dict) -> str | None:
    from services.generation_content_policy import current_content_policy

    if current_content_policy().is_static:
        requested = task.get("staticPaletteFamily")
        families = ("blue", "purple", "warm")
        if requested in families:
            return requested
        seed = task.get("userQuery", "").strip().encode("utf-8")
        return families[int.from_bytes(hashlib.sha256(seed).digest()[:8]) % len(families)]
    query = task.get("userQuery", "")
    if re.search(r"[蓝紫暖冷青绿粉红橙黄黑白深浅]色|#[0-9a-fA-F]{6,8}", query):
        return None
    data = task.get("dataModelSchema", {}).get("data", {})
    roots = set(data) if isinstance(data, dict) else set()
    if len(roots) > 1:
        return None
    selection = load_theme_registry().get("selection", {})
    families = selection.get("familyByDataRoot", {})
    if len(roots) == 1:
        return families.get(next(iter(roots)), selection.get("defaultFamily"))
    return selection.get("defaultFamily")


def _business_token(task: TaskSpec) -> str | None:
    route, _ = PromptBuilder._visual_route(task)
    roots = {root.casefold() for root in PromptBuilder._data_roots(task)}
    # Generic reminder wording in the layout route does not change a health-only business.
    if route == "calendar-event" and roots == {"healthsport"}:
        route = "health-readout"
    selected: str | None = None
    for rule in load_theme_registry().get("selection", {}).get("fusionRouting", []):
        if route not in rule.get("routes", []):
            continue
        matches = True
        for pattern in rule.get("queryAll", []):
            if not re.search(pattern, task.userQuery):
                matches = False
                break
        if matches:
            selected = rule.get("themeId")
            break
    return selected


def fusion_candidate_gate(task: dict, final_layout: str | None) -> dict:
    evidence = {"allowedTokens": [], "reason": None}
    from services.generation_content_policy import current_content_policy, effective_layout_scope

    if current_content_policy().is_static:
        return {**evidence, "reason": "静态内容使用通用渐变，不按业务关键词选择融球"}
    if task.get("size") != "2x2":
        return {**evidence, "reason": "原规则：仅2x2可用融球"}
    if not final_layout:
        return {**evidence, "reason": "缺少定稿Compact内容，使用纯色渐变"}
    try:
        typed_task = TaskSpec.model_validate(task)
        rows = [r for r in parse_compact_dsl_rows(final_layout) if isinstance(r, ComponentRow)]
        layout = match_compact_layout(rows, size="2x2", layout_scope=effective_layout_scope("2x2"))
    except ValueError as exc:
        return {**evidence, "reason": "无法确认定稿内容：" + str(exc)}
    content = [r for r in rows if r.component_type not in {"PillButton", "CircleButton"}]
    visible = _compact_visible_state(content)
    action_count = sum(bool(row.props.get("onClick")) for row in rows)
    business_count = PromptBuilder._data_block_count(typed_task)
    evidence.update(
        {
            "visibleDataPaths": sorted(visible.paths),
            "visibleFieldCount": len(visible.paths),
            "actionCount": action_count,
            "businessCount": business_count,
            "layoutId": layout.layout_id,
        }
    )
    token = _business_token(typed_task)
    if business_count != 1:
        evidence["reason"] = "原规则：不是单业务"
    elif len(visible.paths) > 3:
        evidence["reason"] = "原规则：可见独立字段超过3项"
    elif action_count > 1:
        evidence["reason"] = "原规则：显式动作超过1个"
    elif layout.layout_id in {"S-dual-info", "S-quad-content", "S-title-dual-content"}:
        evidence["reason"] = "原规则：双分区或多组内容"
    elif any(row.component_type in {"EventCard", "SummaryList", "TableText"} for row in rows):
        evidence["reason"] = "原规则：会议时间线或列表"
    elif token is None:
        evidence["reason"] = "原规则：业务没有对应融球"
    else:
        evidence["allowedTokens"] = [token]
    return evidence
