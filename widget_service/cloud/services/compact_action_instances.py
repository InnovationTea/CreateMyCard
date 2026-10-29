"""Compact 规划动作引用；同类候选按本轮序号区分，端侧事件保持原值。"""

from __future__ import annotations

import json
from typing import Any


def plan_action_candidates(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """唯一 ID 沿用旧引用，重复 ID 使用候选在原数组中的序号。"""
    candidates = task.get("eventCandidates")
    if not isinstance(candidates, list):
        return {}
    counts: dict[str, int] = {}
    distinct: list[tuple[int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        if isinstance(identifier, str) and identifier.strip():
            identifier = identifier.strip()
            signature = json.dumps(
                [identifier, candidate.get("call"), candidate.get("args")],
                sort_keys=True,
                ensure_ascii=False,
            )
            if signature in seen:
                continue
            seen.add(signature)
            counts[identifier] = counts.get(identifier, 0) + 1
            distinct.append((index, identifier, candidate))
    result: dict[str, dict[str, Any]] = {}
    for index, identifier, candidate in distinct:
        reference = identifier
        if counts.get(identifier, 0) > 1:
            reference = f"{identifier}#candidate-{index}"
            while reference in counts or reference in result:
                reference += "#"
        result[reference] = candidate
    return result


def action_instance_instruction(task: dict[str, Any]) -> str:
    """只有多参数同类候选或日程详情追加说明，其它 Plan 提示保持不变。"""
    candidates = plan_action_candidates(task)
    repeated: dict[str, dict[str, Any]] = {}
    has_detail = False
    for reference, candidate in candidates.items():
        if reference != candidate.get("id"):
            repeated[reference] = candidate
        if event_card_detail_action(task, reference):
            has_detail = True
    instruction = ""
    if repeated:
        instruction = (
            "同ID多参数候选必须使用本轮实例引用，不自行复用裸ID。引用与完整候选映射："
            + json.dumps(repeated, ensure_ascii=False)
        )
    if has_detail:
        instruction += (
            "日程详情仅选实际展示记录对应的候选实例，不全选候选；"
            "优先推荐EventCard条目点击，动作素材分配null。"
            "明确要求独立按钮时保留按钮；入会、导航等独立操作仍用按钮。"
        )
    return instruction


def plan_action_handlers(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """统一覆盖检查和素材履约使用的动作实例映射。"""
    result: dict[str, dict[str, Any]] = {}
    for reference, candidate in plan_action_candidates(task).items():
        call = candidate.get("call")
        args = candidate.get("args")
        if isinstance(call, str) and isinstance(args, dict):
            result[reference] = {"call": call, "args": args}
    return result


def event_card_detail_action(task: dict[str, Any], reference: str) -> bool:
    """仅登记的日程详情可由 EventCard 条目承载，不按描述扩展操作。"""
    candidate = plan_action_candidates(task).get(reference)
    if candidate is None or candidate.get("id") != "event.viewCalendarEvent":
        return False
    args = candidate.get("args")
    if not isinstance(args, dict):
        return False
    return (
        candidate.get("call") == "clickToIntent" and args.get("intentName") == "ViewCalendarEvent"
    )


def prefers_event_card_item(fact: dict[str, Any]) -> bool:
    """只读取已接受的组件首选，未登记或非法候选不改变原按钮策略。"""
    hints = fact.get("componentHints")
    return isinstance(hints, list) and hints[:1] == ["EventCard"]


def event_card_item_handlers(props: dict[str, Any]) -> list[dict[str, Any]]:
    """只收集 EventCard 条目的点击，不递归接受任意嵌套事件。"""
    result: list[dict[str, Any]] = []
    items = props.get("items")
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        handlers = item.get("onClick")
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if isinstance(handler, dict):
                result.append(handler)
    return result
