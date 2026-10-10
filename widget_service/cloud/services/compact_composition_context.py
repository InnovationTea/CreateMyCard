"""从现有合同提取生成工作表，不改写 DSL，也不另维护布局或机型常量。"""

import copy
import json
from typing import Any

from services.compact_component_runtime import component_visual_recipe, load_visual_recipe_contract
from services.compact_layout_runtime import load_layout_contract
from services.compact_reference_canvas import reference_dimension

_GEOMETRY_KEYS = frozenset({
    "width", "height", "padding", "margin", "itemMargin", "fontSize", "fontWeight",
    "maxLines", "constraintSize", "alignItems", "justifyContent", "textAlign",
})
_RULE_KEYS = (
    "path", "types", "childCount", "childCountMin", "childCountMax", "eventPolicy",
)


def compact_composition_context(size: str, plan: dict[str, Any], task: dict[str, Any]) -> str:
    """提供当前合同的容量与责任清单；参考尺寸只用于核算，不写回产品宽高。"""
    facts = plan.get("info_required", [])
    if not isinstance(facts, list):
        return ""
    actions: set[str] = set()
    titles: list[dict[str, Any]] = []
    names = {"SingleLineTitle", "SecondaryBody", "TableText", "PillButton"}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        action = fact.get("actionId")
        if isinstance(action, str):
            actions.add(action)
        hints = fact.get("componentHints", [])
        if not isinstance(hints, list):
            continue
        for name in hints:
            if isinstance(name, str):
                names.add(name)
        if "SingleLineTitle" in hints:
            titles.append({key: fact[key] for key in ("dataId", "text") if key in fact})

    handlers: list[dict[str, Any]] = []
    candidates = task.get("eventCandidates", [])
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("id") in actions:
                handlers.append(copy.deepcopy(candidate))

    payload = {
        "referenceCanvasOnly": {
            "width": reference_dimension(size, "width"),
            "height": reference_dimension(size, "height"),
        },
        "requiredActionCount": len(actions),
        "requiredActions": handlers,
        "requiredSingleLineTitleBindings": titles,
        "legalLayoutAlternatives": _layout_geometry(size, len(actions)),
        "candidateRecipeParts": _recipe_geometry(size, names),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        "# 本轮组合容量工作表（来自当前运行时合同）\n\n"
        "先为 requiredActions 中每个真实动作预留合法入口及高度；"
        "requiredActionCount 是去重后的真实操作数，不能为填满槽位复制相同按钮；"
        "requiredSingleLineTitleBindings 必须落到 SingleLineTitle.title，"
        "不能仅放在 InfoBlock 或正文里，也不要额外创建重复标题。"
        "从 legalLayoutAlternatives 选择能放下完整信息组的一个布局与一个完整变体，"
        "不能混用不同变体的根节点和子槽；path 为从 root 开始的子节点序号。"
        "referenceBox 与 referenceCanvasOnly 仅用于参考容量核算，绝非输出固定宽高；"
        "承载区仍用 matchParent/layoutWeight，padding、组间距、按钮与文字设计量不变。"
        "candidateRecipeParts 是部件尺寸，不是整组件总高；variants 是对 base 的差量覆盖。"
        "依完整组件合同按 items 数、"
        "行数和横纵排列合计，横排取高度包络，纵排累加高度和间距。不得机械累加所有可选部件。"
        "横排还须按实际权重逐区核对完整值、单位和标签的文字宽度，不能用总宽够用代替子区够用。"
        "数值字段和真实单位优先分别传 value 与 unit；已有格式化字符串保持完整，不拆单位。"
        "若某个横排子区装不下完整读数，不得裁切尾部；改合法分区比例或组件组合后重算宽高。"
        "无法容纳时先改合法组合或布局，不缩字、删事实、删操作或只调权重。"
        "本表只摘要已有合同，不授权新 Props；不要输出本表或任何额外协议字段。\n\n"
        f"```json\n{encoded}\n```"
    )


def _layout_geometry(size: str, action_count: int) -> dict[str, Any]:
    layouts = load_layout_contract().get("layouts", {})
    output: dict[str, Any] = {}
    for name, layout in layouts.items():
        if layout.get("size") != size:
            continue
        count = layout.get("actionCount", {})
        if not count.get("min", 0) <= action_count <= count.get("max", action_count):
            continue
        patterns: list[list[dict[str, Any]]] = []
        for pattern in layout.get("patterns", []):
            rules: list[dict[str, Any]] = []
            for rule in pattern.get("rules", []):
                item = {key: copy.deepcopy(rule[key]) for key in _RULE_KEYS if key in rule}
                props = copy.deepcopy(rule.get("props", {}))
                box: dict[str, Any] = {}
                for axis in ("width", "height"):
                    if axis in props:
                        box[axis] = props.pop(axis)
                if box:
                    item["referenceBox"] = box
                if props:
                    item["fixedProps"] = props
                rules.append(item)
            patterns.append(rules)
        output[name] = patterns
    return output


def _recipe_geometry(size: str, names: set[str]) -> dict[str, Any]:
    registered = load_visual_recipe_contract().get("components", {})
    output: dict[str, Any] = {}
    for name in sorted(names):
        if name not in registered:
            continue
        recipe = component_visual_recipe(name, size=size)
        base = _parts_geometry(recipe)
        geometry: dict[str, Any] = {"base": base}
        variants: dict[str, Any] = {}
        for variant in recipe.get("variants", {}):
            resolved = component_visual_recipe(name, size=size, variant=variant)
            variants[variant] = _geometry_delta(base, _parts_geometry(resolved))
        if variants:
            geometry["variants"] = variants
        output[name] = geometry
    return output


def _geometry_delta(base: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    """变体只携带变化项，避免重复注入完整部件。"""
    output: dict[str, Any] = {}
    for key, value in resolved.items():
        previous = base.get(key)
        if value == previous:
            continue
        if isinstance(value, dict) and isinstance(previous, dict):
            output[key] = _geometry_delta(previous, value)
        else:
            output[key] = value
    return output


def _parts_geometry(recipe: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    metrics = recipe.get("metrics")
    if isinstance(metrics, dict):
        output["metrics"] = copy.deepcopy(metrics)
    for name, part in recipe.get("parts", {}).items():
        styles = part.get("styles", {})
        geometry = {key: copy.deepcopy(value) for key, value in styles.items()
                    if key in _GEOMETRY_KEYS}
        if geometry:
            output[name] = {"component": part.get("component"), "styles": geometry}
    return output
