"""从现有合同提取生成工作表，不改写 DSL，也不另维护布局或机型常量。"""

import copy
import json
import math
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

    layouts = _layout_geometry(size, len(actions))
    payload = {
        "referenceCanvasOnly": {
            "width": reference_dimension(size, "width"),
            "height": reference_dimension(size, "height"),
        },
        "requiredActionCount": len(actions),
        "requiredActions": handlers,
        "requiredSingleLineTitleBindings": titles,
        "legalLayoutAlternatives": layouts,
        "candidateRecipeParts": _recipe_geometry(size, names),
        "ordinaryFactPacking": _fact_packing(size, facts, task),
        "referenceContentBudgets": _content_budgets(size, layouts, len(actions)),
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
        "ordinaryFactPacking 给出完整事实的普通信息组合高度，不强迫把核心主值降为正文；"
        "普通时间、状态等没有真实强调要求时，不因 componentHints 首项就各做一个强调块。"
        "referenceContentBudgets 已扣除区域内边距，localReservations 才是扣标题与本地动作后的余额；"
        "动作若已落在独立动作槽，不在正文区域重复扣除或复制。"
        "先比较普通单列、双列、表格的确切高度与文字宽度，再决定是否保留额外装饰标题。"
        "不要把两个较长 label+value 放在同一短行；长日期和地点用单列并声明允许的两行。"
        "CardButton 完整标签一行放不下时可用 labelLines:2，原字号不变，"
        "两行标签加上下 padding 必须仍在槽位内；不删动作目标文字。"
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
                box.update(copy.deepcopy(rule.get("slotSize", {})))
                if box:
                    item["referenceBox"] = box
                if props:
                    item["fixedProps"] = props
                rules.append(item)
            patterns.append(rules)
        output[name] = patterns
    return output


def _schema_field(schema: Any, path: str) -> dict[str, Any]:
    value = schema
    for part in path.removeprefix("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
        elif isinstance(value, dict):
            if part.isdigit() and "items" in value:
                value = value.get("items")
            else:
                value = value.get(part)
        else:
            return {}
    return value if isinstance(value, dict) else {}


def _fact_packing(
    size: str, facts: list[Any], task: dict[str, Any]
) -> dict[str, Any]:
    """计算普通文本候选，不强制语义降级，也不把 sampleValue 写入输出。"""
    required: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict) or fact.get("actionId"):
            continue
        item = {key: copy.deepcopy(fact[key]) for key in ("requirement", "dataId", "text")
                if key in fact}
        path = fact.get("dataId")
        if isinstance(path, str):
            field = _schema_field(task.get("dataModelSchema"), path)
            item["fieldType"] = field.get("type")
            item["pressureSampleOnly"] = copy.deepcopy(field.get("sampleValue"))
            item["meaning"] = field.get("description")
        required.append(item)
    options: list[dict[str, Any]] = []
    count = len(required)
    if 1 <= count <= 4:
        variant = "multiline" if count > 2 else None
        recipe = component_visual_recipe("SecondaryBody", size=size, variant=variant)
        text = recipe.get("parts", {}).get("text", {}).get("styles", {})
        root = recipe.get("parts", {}).get("root", {}).get("styles", {})
        height = text.get("height", 0) / text.get("maxLines", 1)
        gap = root.get("itemMargin", 0)
        for columns in (1, 2):
            rows = math.ceil(count / columns)
            for lines in (1, 2):
                options.append({
                    "component": "SecondaryBody", "role": "supporting",
                    "items": count, "columns": columns, "maxLinesPerValue": lines,
                    "rows": rows, "requiredHeight": rows * height * lines + (rows - 1) * gap,
                    "fontSizeUnchanged": text.get("fontSize"),
                    "widthCondition": "Each label plus complete value must fit its own column; "
                                      "two columns subtract the separator before equal allocation",
                })
    if 2 <= count <= 3:
        variant = "compact" if count == 3 else None
        recipe = component_visual_recipe("TableText", size=size, variant=variant)
        parts = recipe.get("parts", {})
        height = parts.get("row", {}).get("styles", {}).get("height", 0)
        gap_key = "threeRowGap" if count == 3 else "twoRowGap"
        gap = recipe.get("metrics", {}).get(gap_key, 0)
        options.append({"component": "TableText", "items": count,
                        "requiredHeight": height * count + gap * (count - 1),
                        "widthCondition": (
                            "Natural label plus gap plus complete value fits one row; "
                            "use only semantically related attributes"
                        )})
    return {"requiredFacts": required, "options": options,
            "warning": "Do not shrink existing focal fonts or discard facts to select an option. "
                       "Pressure samples are not real device measurements or static bindings. "
                       "For more than four facts split legal semantic groups and sum all heights."}


def _padding_pair(value: Any, axis: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) * 2
    if isinstance(value, dict):
        sides = ("left", "right") if axis == "width" else ("top", "bottom")
        return sum(float(value.get(side, 0)) for side in sides)
    return 0.0


def _content_budgets(
    size: str, layouts: dict[str, Any], action_count: int
) -> list[dict[str, Any]]:
    """列出合同参考区域的容量算式，不创建几何或锁定业务骨架。"""
    title = component_visual_recipe("SingleLineTitle", size=size)
    button = component_visual_recipe("PillButton", size=size)
    body = component_visual_recipe("SecondaryBody", size=size)
    title_height = title.get("parts", {}).get("root", {}).get("styles", {}).get("height", 0)
    button_height = button.get("parts", {}).get("root", {}).get("styles", {}).get("height", 0)
    group_gap = body.get("parts", {}).get("root", {}).get("styles", {}).get("itemMargin", 0)
    output: list[dict[str, Any]] = []
    for name, patterns in layouts.items():
        for index, rules in enumerate(patterns, start=1):
            for rule in rules:
                if rule.get("eventPolicy") == "require":
                    continue
                box = rule.get("referenceBox", {})
                if not rule.get("path") and len(rules) == 1:
                    box = {"width": reference_dimension(size, "width"),
                           "height": reference_dimension(size, "height")}
                width, height = box.get("width"), box.get("height")
                if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                    continue
                props = rule.get("fixedProps", {})
                padding = props.get("padding", 0)
                inner_width = width - _padding_pair(padding, "width")
                inner_height = height - _padding_pair(padding, "height")
                gap = props.get("itemMargin", group_gap)
                reservations: list[dict[str, Any]] = []
                for titles in (0, 1):
                    for actions in range(min(action_count, 2) + 1):
                        reserved = titles * title_height + actions * button_height
                        remaining = inner_height - reserved - gap * (titles + actions)
                        reservations.append({"localTitles": titles, "localPillActions": actions,
                                             "bodyHeightAfterReservations": remaining})
                output.append({"layout": name, "variant": index, "path": rule.get("path"),
                               "innerWidth": inner_width, "innerHeight": inner_height,
                               "groupGapForArithmeticOnly": gap,
                               "localReservations": reservations,
                               "condition": (
                                   "Respect the complete variant child roles/counts. "
                                   "Do not reserve a title/action again inside a dedicated "
                                   "body or beside an already separate action slot."
                               )})
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
