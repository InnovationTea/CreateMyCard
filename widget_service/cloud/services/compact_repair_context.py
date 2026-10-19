"""修复用合同与拓扑摘要；不承担校验、字段推断或删除授权。"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from app.logger import logger

JOINT_RECOMPOSITION_INSTRUCTION = (
    "此前布局已失败，本轮把结构、容量、事实、动作和素材作为同一重组问题处理，"
    "不要因错误类别切换退回单点修补。先按全部保留事实和完整动作计算各区预算，"
    "比较不同合法承载组合；放不下的旧堆叠不能只改ID、间距或包装层。"
    "仅在合同允许且不是用户必需标题时移除装饰标题；不缩固定字号，不削减事实或动作。"
    "随后一起复查树闭合、事实唯一可见、动作参数准确与入口可达、动作图标分配和横纵容量。"
)


def repair_topology_fingerprint(source: str) -> str | None:
    """忽略 ID 和配色；保留组件、布局角色、挂接及行数配置。解析不明时不推断。"""
    components: dict[str, list[Any]] = {}
    try:
        for line in source.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, list):
                return None
            if len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/"):
                continue
            if len(row) not in {3, 4} or not isinstance(row[1], str):
                return None
            if len(row) == 4 and not isinstance(row[3], list):
                return None
            if not isinstance(row[0], str) or not isinstance(row[2], dict):
                return None
            if row[0] in components:
                return None
            components[row[0]] = row
    except json.JSONDecodeError as exc:
        logger.debug("repair_topology_unavailable exception_type={}", type(exc).__name__)
        return None
    if "root" not in components:
        return None
    visited: set[str] = set()

    def shape(identifier: str, stack: tuple[str, ...]) -> list[Any]:
        if identifier in stack or len(stack) >= 48:
            return ["cycle_or_depth_limit"]
        row = components.get(identifier)
        if row is None:
            return ["missing_reference"]
        if identifier in visited:
            return ["shared_reference"]
        visited.add(identifier)
        props = row[2]
        configuration = {}
        for key in ("layout", "variant", "orientation", "columns", "density", "maxLines"):
            if key in props:
                configuration[key] = props.get(key)
        items = props.get("items")
        if isinstance(items, list):
            lines = []
            for item in items:
                lines.append(item.get("maxLines", 1) if isinstance(item, dict) else None)
            configuration["itemLines"] = lines
        children = row[3] if len(row) == 4 and isinstance(row[3], list) else []
        child_shapes = []
        for child in children:
            if not isinstance(child, str):
                child_shapes.append(["invalid_reference"])
                continue
            child_shapes.append(shape(child, (*stack, identifier)))
        return [row[1], configuration, child_shapes]

    rooted = shape("root", ())
    if len(visited) != len(components):
        return None
    encoded = json.dumps(rooted, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def joint_repair_contract(
    plan: dict[str, Any], task: dict[str, Any], omissions: list[dict[str, Any]],
) -> dict[str, Any]:
    """保留原合同真实值及 None；省略清单不能授权删除 Action。"""
    plan_facts = plan.get("info_required", [])
    omitted = set()
    authorized = []
    for omission in omissions:
        index = omission.get("factIndex")
        if isinstance(index, bool) or not isinstance(index, int):
            continue
        if not 0 <= index < len(plan_facts):
            continue
        fact = plan_facts[index]
        if not isinstance(fact, dict) or "actionId" in fact:
            continue
        omitted.add(index)
        authorized.append(copy.deepcopy(omission))
    facts = []
    action_ids: set[str] = set()
    for index, fact in enumerate(plan_facts):
        if not isinstance(fact, dict):
            continue
        action = fact.get("actionId")
        if isinstance(action, str):
            action_ids.add(action)
            continue
        if index in omitted:
            continue
        protected: dict[str, Any] = {"factIndex": index}
        for key in ("requirement", "priority", "dataId", "text"):
            if key in fact:
                protected[key] = copy.deepcopy(fact.get(key))
        facts.append(protected)
    actions = []
    for candidate in task.get("eventCandidates", []):
        if isinstance(candidate, dict) and candidate.get("id") in action_ids:
            actions.append(copy.deepcopy(candidate))
    assignments = plan.get("assetAssignments")
    selected_assets: set[str] = set()
    if isinstance(assignments, dict):
        selections = list(assignments.get("actions", []))
        selections.append(assignments.get("title"))
        for selection in selections:
            if isinstance(selection, dict):
                asset_id = selection.get("assetId")
                if isinstance(asset_id, str):
                    selected_assets.add(asset_id)
    assigned_assets = []
    for candidate in task.get("assetCandidates", []):
        if not isinstance(candidate, dict):
            continue
        matches_id = candidate.get("id") in selected_assets
        matches_src = candidate.get("src") in selected_assets
        if matches_id or matches_src:
            assigned_assets.append(copy.deepcopy(candidate))
    action_instruction = (
        "Action按原候选完整复制call和args；按钮从root可达，"
        "分配给动作的素材必须用于对应按钮，不能被信息图标或标题抢占。"
    )
    whole_card_action_id = plan.get("wholeCardActionId")
    if isinstance(whole_card_action_id, str):
        action_instruction = (
            "wholeCardActionId指定的详情保留唯一root.onClick及完整call和args，"
            "不补回按钮、按钮图标或子点击；整卡承载不占按钮高度。"
        )
    result = {
        "facts": facts,
        "actionIds": sorted(action_ids),
        "actions": actions,
        "assetAssignments": copy.deepcopy(plan.get("assetAssignments")),
        "assignedAssets": assigned_assets,
        "approvedOmissions": authorized,
        "instruction": (
            "仅 approvedOmissions 中的非Action事实获准省略。其它事实保留标签、完整值、单位及绑定，"
            "不冻结原组件软候选。"
            f"{action_instruction}"
            "按本轮scope保护未受影响区域；重组结束同时对照本清单，不以当前错误消失代替整体核对。"
        ),
    }
    if isinstance(whole_card_action_id, str):
        result["wholeCardActionId"] = whole_card_action_id
    return result
