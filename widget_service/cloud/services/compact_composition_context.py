"""从现有合同提取生成工作表，不改写 DSL，也不另维护布局或机型常量。"""

import ast
import copy
import json
import math
import re
from typing import Any

from services.compact_component_runtime import (
    component_visual_recipe,
    load_visual_recipe_contract,
    secondary_body_variant,
    text_block_full_width_budget,
    text_block_width_contract,
)
from services.compact_composition_planner import (
    _schema_value,
    _text_width,
    composition_structure_blueprint,
    composition_text_width_conflicts,
    compound_duration_bindings,
    is_compound_duration_text,
    quantitative_main_bindings,
)
from services.compact_layout_runtime import load_layout_contract
from services.compact_reference_canvas import reference_dimension
from services.display_text import concatenated_display_text
from services.event_matching import event_handlers_match

_GEOMETRY_KEYS = frozenset({
    "width", "height", "padding", "margin", "itemMargin", "fontSize", "fontWeight",
    "maxLines", "constraintSize", "alignItems", "justifyContent", "textAlign",
})
_RULE_KEYS = (
    "path", "types", "childCount", "childCountMin", "childCountMax", "eventPolicy",
)


def compact_text_block_capacity_context(size: str) -> str:
    """提供必需的组件容量边界，不依赖可选的全量运行时工作表。"""
    if size != "2x4":
        return ""
    contract = text_block_width_contract(size)
    layouts = _layout_geometry(size, None)
    patterns = layouts.get("W-top-bottom", [])
    widths: list[float] = []
    for area in _content_budgets(size, {"W-top-bottom": patterns}, 0):
        width = area.get("innerWidth")
        if isinstance(width, (int, float)):
            widths.append(float(width))
    if not widths:
        raise ValueError("W-top-bottom has no known TextBlock width budget.")
    available = max(widths)
    budget = text_block_full_width_budget(available, available)
    requirements: list[str] = []
    for count in range(contract.minimum_items, contract.maximum_items + 1):
        requirements.append(f"{count}项至少{contract.required_width(count):g}vp")
    return (
        "# TextBlock 槽位容量合同\n\n"
        f"按当前 Recipe 核算：{'；'.join(requirements)}。"
        f"W-top-bottom.details 的实际槽宽为{available:g}vp，横向校验预算上界为{budget:g}vp，"
        f"最多容纳{contract.capacity_for_width(budget)}项，较窄槽位须按实际宽度重新核算。"
        "280vp预算只允许满宽四项TextBlock最多4vp的差额，不改变实际槽位或组件样式。"
        "组件项目数上限不代表当前槽位放得下；只在已登记的 details 槽使用。"
        "放不下时按全部事实重新选择合法组件与布局，不能删项、隐藏绑定、缩字或缩间距。"
        "若合并紧密相关信息，必须保留每项标签、完整值、单位和独立绑定，并复核文字宽度。"
    )


def compact_composition_context(
    size: str, plan: dict[str, Any], task: dict[str, Any],
    *, constructive_result: dict[str, Any] | None = None,
) -> str:
    """只交接本轮信息责任；容量枚举留在程序内部，不重复给模型选择。"""
    del constructive_result
    facts = plan.get("info_required", [])
    if not isinstance(facts, list):
        return ""
    actions: set[str] = set()
    titles: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        action = fact.get("actionId")
        if isinstance(action, str):
            actions.add(action)
        hints = fact.get("componentHints", [])
        if isinstance(hints, list) and "SingleLineTitle" in hints:
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
        "quantitativeMainBindings": quantitative_main_bindings(plan, task),
        "quantitativeMainFontSize": component_visual_recipe(
            "EmphasizedData", size=size,
        ).get("parts", {}).get("value", {}).get("styles", {}).get("fontSize"),
    }
    duration_paths = compound_duration_bindings(plan, task)
    duration_instruction = ""
    if duration_paths:
        payload["compoundDurationBindings"] = duration_paths
        duration_instruction = (
            "compoundDurationBindings已包含多段数量与时间单位，属于完整文本读数；"
            "作为主信息用EmphasisText.mainText的固定18fp规格，不用30fp EmphasizedData。"
            "作为辅助信息沿用原正文规格；标签加完整时长单行放不下时用合法两行并预留行高，"
            "或在所属区域重排。保留整个原绑定与所有单位，不截样值、不伪造分段字段。\n\n"
        )
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        "# 本轮执行约束\n\n"
        "落实已接受 Plan；compositionRecovery 提供完整参考方案时实现该方案，"
        "未提供完整方案时按诊断重新合组，不沿用已失效旧参考或混用变体。"
        "事实和真实动作全部保留；标题绑定落到 SingleLineTitle.title。"
        "不额外叠加装饰标题、重复按钮或重复读数。区域自适应，正文承接标题、动作及固定间距"
        "扣除后的剩余空间，按钮在所属区底部；文字间距、字号、图标、按钮高度不随区域拉伸。"
        "参考尺寸仅用于核算，不作为输出固定宽高。完整标签、值、单位仍须可读，不缩字、删信息"
        "或裁切。按当前组件合同生成 Props，不输出预算或参考字段。\n\n"
        "完整展示文案包括对象标签、前缀、值和单位；不要只按裸值占宽。"
        "固定单行主文字放不下必要前缀时，在合法承载区拆为原字号的独立行，"
        "不塞入更小字号的次文字。窄列中 label 与 value 共用文字宽度；"
        "完整文案放不下时改合法分行或分区，不靠 clip、maxLines:1 隐藏尾字。\n\n"
        "量化主值与普通状态是不同职责：主读数不得合并进 InfoBlock.secondaryText、"
        "EmphasisText.secondaryText 或 metadata。真实数字比例指标需要主值规格时，"
        "使用能容纳完整对象标签及读数的 EmphasizedData；单位依据字段合同，"
        "不把数值改成状态的小字补充，也不以圆环代替可读读数。"
        "长静态正文优先在原字号正文组件内用单列、合法两行；固定单行组件不能"
        "靠新增空白高度获得第二行。长强调说明可拆成同字号完整上下文行和读数行，"
        "或重选更宽分区，不能把统计范围挪成小字。quantitativeMainBindings明确的数值主值"
        "按quantitativeMainFontSize显示，不能改为普通正文或较小强调文字；"
        "对象名称独立可读，长统计读数可保持主值规格拆为两行。\n\n"
        f"{duration_instruction}```json\n{encoded}\n```"
    )


def composition_implementation_conflicts(plan: dict[str, Any]) -> list[str]:
    """识别软方案的明确冲突；父子分配同时核算，不新增发布校验。"""
    composition = plan.get("composition")
    if not isinstance(composition, dict):
        notes = plan.get("compositionNotes", [])
        return list(notes) if isinstance(notes, list) else []
    if composition.get("layout") == "W-top-bottom":
        if any(fact.get("actionId") for fact in plan.get("info_required", [])):
            return ["W-top-bottom cannot implement independent action buttons; regroup "
                    "into an action-compatible layout without deleting actions"]
    layout = load_layout_contract().get("layouts", {}).get(composition.get("layout"), {})
    patterns = layout.get("patterns", [])
    variant = composition.get("variant")
    if not isinstance(variant, int) or not 1 <= variant <= len(patterns):
        return ["composition variant must be rebuilt from the current contract"]
    rules = patterns[variant - 1].get("rules", [])
    directions = {}
    for rule in rules:
        types = rule.get("types", [])
        directions[tuple(rule.get("path", []))] = types[0] if types else None
    regions = {}
    conflicts: list[str] = []
    for region in composition.get("regions", []):
        path = tuple(region.get("path", []))
        if layout.get("size") == "2x2" or composition.get("layout", "").startswith("S-"):
            for group in region.get("groups", []):
                conflict = group.get("implementationConflict")
                if isinstance(conflict, str):
                    conflicts.append(conflict)
        if path in regions:
            conflicts.append(f"duplicate region assignment at {list(path)}")
        regions[path] = region
    occupied: dict[tuple[int, ...], float] = {}
    for path in sorted(regions, key=len, reverse=True):
        region = regions.get(path)
        own_height = region.get("requiredHeight")
        capacity = region.get("referenceHeight")
        if not isinstance(own_height, (int, float)) or not isinstance(capacity, (int, float)):
            continue
        children = []
        for child_path, child_height in occupied.items():
            if len(child_path) <= len(path) or child_path[:len(path)] != path:
                continue
            intermediate = False
            for other in regions:
                if len(path) < len(other) < len(child_path):
                    if other[:len(path)] == path and child_path[:len(other)] == other:
                        intermediate = True
                        break
            if not intermediate:
                children.append(child_height)
        total = own_height
        if children and directions.get(path) == "Column":
            gap = region.get("gap", 0)
            extra_gaps = len(children) if region.get("groups") else len(children) - 1
            total += sum(children) + gap * max(0, extra_gaps)
        elif children:
            total = max(total, max(children))
        occupied[path] = total
        tolerance = 2.0 if layout.get("size") == "2x2" else 0.0
        if total > capacity + tolerance:
            action_paths = [tuple(rule.get("path", [])) for rule in rules
                            if rule.get("eventPolicy") == "require"]
            content_paths = []
            if composition.get("layout", "").startswith("S-"):
                for rule in rules:
                    child_path = tuple(rule.get("path", []))
                    if len(child_path) != len(path) + 1 or child_path[:len(path)] != path:
                        continue
                    if rule.get("types") != ["Column"]:
                        continue
                    if any(action[:len(child_path)] == child_path for action in action_paths):
                        continue
                    content_paths.append(list(child_path))
            conflicts.append(
                f"region {list(path)} including nested assignments requires {total:g}vp "
                f"within {capacity:g}vp; old grouping is not executable"
                + (f". Assign content to its pure content slot {content_paths}, reserving "
                   "the separate action slot once; regroup all facts at original fonts"
                   if content_paths else "")
            )
    return conflicts


def composition_recovery_context(
    size: str, plan: dict[str, Any], constructive_result: dict[str, Any],
    *, task: dict[str, Any] | None = None,
    implementation_conflicts: list[str] | None = None,
) -> dict[str, Any] | None:
    """把冲突软方案的完整替代落点交给生成，不改硬事实或已闭合方案。"""
    conflicts = composition_implementation_conflicts(plan)
    if implementation_conflicts:
        conflicts.extend(implementation_conflicts)
    if task is not None:
        conflicts.extend(composition_text_width_conflicts(size, plan, task))
    if not conflicts:
        return None
    candidates = constructive_result.get("candidates", [])
    result: dict[str, Any] = {
        "status": "recompose_conflicting_plan",
        "conflicts": conflicts,
        "instruction": (
            "旧 composition 是不可执行的诊断，不是必须照抄的结构。"
            "保留全部 info_required 及真实动作、主值字号，整体落实下列一个完整组合的"
            "布局变体、path、directChildren 包装和 rows 横纵关系；不要给旧超高树调权重。"
            "不得额外叠加候选未预留的装饰标题；必要标题事实仍按指定组件显示。"
            "referenceWidth/Height 只用于核算，区域用 matchParent/layoutWeight，"
            "横排行宽比例转成 layoutWeight，不写死区域宽高；固定设计量不变。"
            "核对标签、单位、进度范围和动作完整名称；若完整文字不满足预算，"
            "可改用另一个完整合法组合并复算，不能缩字、删信息或截断。"
            "structureBlueprint 明确完整父子节点、直属 children 和组件合组，"
            "按引用构建一棵树，不能把 Row 子组另拆成多行或省略前景包装。"
            "单列能放下时不要改回窄双列；未知标签仍需核算。"
            "groupParameters 是组合说明而非可照抄的全部 Props，"
            "事实索引需转换成真实绑定，字段合同单位需解析成合法 unit；"
            "requiresObjectCaption=true 是已预算的必要对象标题，按meaning填写最短准确名称；"
            "它没有新增硬事实，不能省掉，也不能用连接状态代替电量对象。"
            "不得把索引、预算、样值等参考字段输出到 DSL。"
            "横排各子节点落实 suggestedLayoutProps 中的 matchParent/比例权重，"
            "不能让自然宽度的表达式挤占相邻事实。displayBudget 核算的是原值；"
            "最终前缀、标签和单位也必须在原字号下占预算，不能越过 additionalTextWidth。"
            "若必要上下文放不下，可移入已预留且没有硬标题绑定的标题位，"
            "或换完整合法组合；不删必要语义，不替换必需标题。"
            "SecondaryBody 按最终行布局使用单行14/19或多行12/16，核心组件字号保持原 Recipe。"
        ),
    }
    if candidates:
        selected = copy.deepcopy(candidates[0])
        for region in selected.get("regions", []):
            for group in region.get("groups", []):
                group.pop("pressureOnly", None)
        result["referenceComposition"] = selected
        result["structureBlueprint"] = composition_structure_blueprint(size, selected)
        alternatives = _layout_geometry(size, None).get(selected.get("layout"), [])
        variant = selected.get("variant")
        if isinstance(variant, int) and 1 <= variant <= len(alternatives):
            result["completeLayoutRules"] = alternatives[variant - 1]
    else:
        result["searchStatus"] = constructive_result.get("status")
        result["unresolved"] = constructive_result.get("unresolved", [])
        result["instruction"] += "有限搜索未给出完整解，仍应按当前合同重新合组，不提前失败。"
    return result


def repair_boolean_display_samples(source: str, task: dict[str, Any]) -> dict[str, str]:
    """只读原源的简单完整布尔映射，核算两支最宽文字，不执行表达式或猜文案。"""
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
    from services.compact_high_level_components import CompactDslConversionError, ComponentRow

    try:
        rows = parse_compact_dsl_rows(source)
    except CompactDslConversionError:
        return {}  # 结构未能解析时继续原修复，不新增搜索失败。
    literal = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
    pattern = re.compile(
        r"\s*\{\{\s*\$\{(?P<path>/[^{}]+)\}\s*\?\s*"
        + rf"(?P<yes>{literal})\s*:\s*(?P<no>{literal})\s*\}}\}}\s*"
    )
    visible = {
        "title", "mainText", "secondaryText", "value", "primaryText", "displayValue",
        "supportingText", "text", "content", "label", "time", "location",
    }
    samples: dict[str, str] = {}

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in visible or key == "items":
                    collect(item)
        elif isinstance(value, str):
            match = pattern.fullmatch(value)
            if match is None:
                return
            path = match.group("path")
            field = _schema_value(task, path)
            if field.get("type") != "boolean":
                return
            branches = []
            for name in ("yes", "no"):
                try:
                    text = ast.literal_eval(match.group(name))
                except (SyntaxError, ValueError):
                    return
                if not isinstance(text, str) or not text.strip():
                    return
                branches.append(text)
            widest = max(branches, key=lambda text: _text_width(text, 1))
            previous = samples.get(path)
            if previous is None or _text_width(widest, 1) > _text_width(previous, 1):
                samples[path] = widest

    for row in rows:
        if isinstance(row, ComponentRow):
            collect(row.props)
    return samples


def repair_display_samples(source: str, task: dict[str, Any]) -> dict[str, str]:
    """读取已写出的完整正文压力；不执行表达式，不跨项借标签，不修改源。"""
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
    from services.compact_high_level_components import CompactDslConversionError, ComponentRow

    samples = repair_boolean_display_samples(source, task)
    try:
        rows = parse_compact_dsl_rows(source)
    except CompactDslConversionError:
        return samples
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        values: list[dict[str, Any]] = []
        if row.component_type == "SecondaryBody":
            items = row.props.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        values.append(item)
        elif row.component_type == "EmphasisText":
            values.append({"value": row.props.get("mainText")})
        elif row.component_type == "EmphasizedData":
            values.append({"value": row.props.get("value")})
        for item in values:
            display = _literal_display_sample(item.get("value"), task)
            if display is None:
                continue
            path, text = display
            label = item.get("label")
            if isinstance(label, str) and "{{" not in label:
                text = label + " " + text
            previous = samples.get(path)
            if previous is None or _text_width(text, 1) > _text_width(previous, 1):
                samples[path] = text
    return samples


def repair_display_roles(source: str, *, size: str | None = None) -> dict[str, dict[str, Any]]:
    """保留失败源的主文字规格，不能因容量恢复把18fp主文变成14fp正文。"""
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
    from services.compact_high_level_components import CompactDslConversionError, ComponentRow

    try:
        rows = parse_compact_dsl_rows(source)
    except CompactDslConversionError:
        return {}
    roles: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_type not in {"EmphasisText", "EmphasizedData", "SecondaryBody"}:
            continue
        if row.component_type == "SecondaryBody":
            items = row.props.get("items", [])
            if not isinstance(items, list):
                continue
            values = [item.get("value") for item in items if isinstance(item, dict)]
        else:
            key = "mainText" if row.component_type == "EmphasisText" else "value"
            values = [row.props.get(key)]
        for value in values:
            encoded = json.dumps(value, ensure_ascii=False)
            paths = re.findall(r"\$\{(/[^{}]+)\}", encoded)
            if isinstance(value, dict) and isinstance(value.get("path"), str):
                paths = [value.get("path")]
            if len(paths) == 1:
                priority = {"EmphasizedData": 3, "EmphasisText": 2, "SecondaryBody": 1}
                previous = roles.get(paths[0], {})
                if priority.get(previous.get("component"), 0) > priority.get(row.component_type, 0):
                    continue
                roles[paths[0]] = {
                    "component": row.component_type,
                    "displayExpression": value,
                }
                if size == "2x2":
                    variant = None
                    part = "main" if row.component_type == "EmphasisText" else "value"
                    if row.component_type == "SecondaryBody":
                        variant = secondary_body_variant(items, row.props.get("columns", 2))
                        part = "text"
                    recipe = component_visual_recipe(row.component_type, size=size, variant=variant)
                    roles[paths[0]]["fontSize"] = recipe.get("parts", {}).get(part, {}).get(
                        "styles", {},
                    ).get("fontSize")
                if row.component_type == "SecondaryBody":
                    for item in items:
                        if isinstance(item, dict) and item.get("value") == value:
                            roles[paths[0]]["displayLabel"] = item.get("label")
    return roles


def retain_original_small_display_roles(
    reference: dict[str, dict[str, Any]], source: str, task: dict[str, Any] | None = None,
) -> None:
    """逐路径保留首次可读规格；不以中途失败输出覆盖原字号。"""
    for path, role in repair_display_roles(source, size="2x2").items():
        if role.get("component") == "EmphasizedData" and task is not None:
            displayed = _literal_display_sample(role.get("displayExpression"), task)
            if displayed is not None and is_compound_duration_text(displayed[1]):
                continue  # 此选型本来不合法，不把错误30fp冻结成必须保留的规格。
        if path not in reference:
            reference[path] = copy.deepcopy(role)


def literal_display_parts(value: Any, task: dict[str, Any]) -> list[dict[str, str]]:
    """仅分离原纯文字前缀，动态路径和后缀原样保留；未知表达式不尝试。"""
    displayed = _literal_display_sample(value, task)
    if displayed is None or not isinstance(value, str):
        return []
    path, sample = displayed
    marker = "${" + path + "}"
    body = value.strip().removeprefix("{{").removesuffix("}}").strip()
    before, _, after = body.partition(marker)
    literal = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
    prefix = "".join(ast.literal_eval(match.group(0)) for match in re.finditer(literal, before))
    if not prefix.strip():
        return []
    return [
        {"text": prefix.strip(), "sample": prefix.strip()},
        {"text": "{{ " + marker + after + " }}", "sample": sample[len(prefix):].strip()},
    ]


def repair_action_labels(source: str, task: dict[str, Any]) -> dict[str, str]:
    """按完整事件匹配失败源按钮原文，不从业务名推断或缩短标签。"""
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
    from services.compact_high_level_components import CompactDslConversionError, ComponentRow

    try:
        rows = parse_compact_dsl_rows(source)
    except CompactDslConversionError:
        return {}
    labels: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        label = row.props.get("label")
        handlers = row.props.get("onClick", [])
        if not isinstance(label, str) or "{{" in label:
            continue
        if not isinstance(handlers, list):
            continue
        for event in task.get("eventCandidates", []):
            if not isinstance(event, dict):
                continue
            event_id = event.get("id")
            if not isinstance(event_id, str):
                continue
            handler = {"call": event.get("call"), "args": event.get("args")}
            for actual in handlers:
                if not isinstance(actual, dict):
                    continue
                if event_handlers_match(actual, handler):
                    labels[event_id] = label
                    break
    return labels


def _literal_display_sample(value: Any, task: dict[str, Any]) -> tuple[str, str] | None:
    """只接受一个原路径和字符串字面量的加法串；函数、算术和多路径都不猜测。"""
    if isinstance(value, dict) and set(value) == {"path"}:
        path = value.get("path")
        if not isinstance(path, str):
            return None
        sample = _schema_value(task, path).get("sampleValue")
        if isinstance(sample, (str, int, float)) and not isinstance(sample, bool):
            return path, str(sample)
        return None
    if not isinstance(value, str) or not value.strip().startswith("{{"):
        return None
    expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if expression is None:
        return None
    literal = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
    token = re.compile(rf"(?P<path>\$\{{(/[^{{}}]+)\}})|(?P<literal>{literal})")
    body = expression.group(1).strip()
    paths: list[str] = []
    parts: list[str] = []
    offset = 0
    for match in token.finditer(body):
        separator = body[offset:match.start()].strip()
        if separator != ("+" if parts else ""):
            return None
        raw_path = match.group("path")
        if raw_path is not None:
            path = raw_path.removeprefix("${").removesuffix("}")
            sample = _schema_value(task, path).get("sampleValue")
            if isinstance(sample, bool) or not isinstance(sample, (str, int, float)):
                return None
            paths.append(path)
            parts.append(str(sample))
        else:
            try:
                text = ast.literal_eval(match.group("literal"))
            except (SyntaxError, ValueError):
                return None
            if not isinstance(text, str):
                return None
            parts.append(text)
        offset = match.end()
    if len(paths) != 1 or body[offset:].strip():
        return None
    return paths[0], "".join(parts)


def small_card_display_text(value: Any, task: dict[str, Any]) -> str | None:
    """小卡完整文字压力：只读字符串连接或简单布尔映射，不执行表达式。"""
    if isinstance(value, dict):
        displayed = _literal_display_sample(value, task)
        return displayed[1] if displayed is not None else None
    if not isinstance(value, str):
        return None
    if "{{" not in value:
        return value
    expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if expression is None:
        return None
    literal = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
    comparison = re.fullmatch(
        r"\s*\$\{(/[^{}]+)\}\s*(?:==|!=)\s*-?\d+(?:\.\d+)?\s*\?\s*("
        + literal + r")\s*:\s*(" + literal + r")\s*", expression.group(1),
    )
    if comparison is not None:
        schema_type = _schema_value(task, comparison.group(1)).get("type")
        if schema_type not in {"integer", "number"}:
            return None
        try:
            branches = [ast.literal_eval(comparison.group(index)) for index in (2, 3)]
        except (SyntaxError, ValueError):
            return None
        return max(branches, key=lambda text: _text_width(text, 1))
    boolean = re.fullmatch(
        r"\s*\$\{(/[^{}]+)\}\s*\?\s*(" + literal + r")\s*:\s*(" + literal + r")\s*",
        expression.group(1),
    )
    if boolean is not None:
        if _schema_value(task, boolean.group(1)).get("type") != "boolean":
            return None
        try:
            branches = [ast.literal_eval(boolean.group(index)) for index in (2, 3)]
        except (SyntaxError, ValueError):
            return None
        return max(branches, key=lambda text: _text_width(text, 1))
    return concatenated_display_text(
        value, lambda path: _schema_value(task, path).get("sampleValue"),
    )


def compact_plan_capacity_context(size: str) -> str:
    """在选型前提供完整容量合同，不依据尚未提交的事实预锁骨架。"""
    layouts = _layout_geometry(size, None)
    registered = load_visual_recipe_contract().get("components", {})
    packing: dict[str, Any] = {}
    for count in range(1, 5):
        packing[str(count)] = _packing_options(size, count)
    payload = {
        "referenceCanvasOnly": {
            "width": reference_dimension(size, "width"),
            "height": reference_dimension(size, "height"),
        },
        "layouts": layouts,
        "recipeParts": _recipe_geometry(size, set(registered)),
        "ordinaryPackingByItemCount": packing,
        "contentBudgets": _content_budgets(size, layouts, 2),
    }
    return (
        "# Plan 分区与合组容量合同\n\n"
        "先确定必要事实和动作，再从 layouts 选一个完整变体；variant 从1开始，"
        "path 从root子序号开始。提交 composition 的每组事实索引和可见属性落点。"
        "正文、标题、按钮都计入各区预算，不能将动作放到另一对象或复制填槽。"
        "布局高度不等于文字高度；recipeParts 是部件，按实际条数/行数/方向合计。"
        "contentBudgets 已扣区域内边距，不重复扣；独立动作区也不重复预留。"
        "长日期、地点、状态、带单位读数逐项核对自己列宽，不默认使用双列。"
        "额外高度留在正文承载区，文字间距与字号保持原设计；"
        "参考数字仅用于容量核算，区域仍自适应。全区预算不成立时先重选组合再提交。\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n```"
    )


def _layout_geometry(size: str, action_count: int | None) -> dict[str, Any]:
    layouts = load_layout_contract().get("layouts", {})
    output: dict[str, Any] = {}
    for name, layout in layouts.items():
        if layout.get("size") != size:
            continue
        count = layout.get("actionCount", {})
        if action_count is not None and not (
            count.get("min", 0) <= action_count <= count.get("max", action_count)
        ):
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
    return {"requiredFacts": required, "options": _packing_options(size, len(required)),
            "warning": "Do not shrink existing focal fonts or discard facts to select an option. "
                       "Pressure samples are not real device measurements or static bindings. "
                       "For more than four facts split legal semantic groups and sum all heights."}


def _packing_options(size: str, count: int) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if 1 <= count <= 4:
        for columns in (1, 2):
            rows = math.ceil(count / columns)
            for lines in (1, 2):
                variant = secondary_body_variant([{"maxLines": lines}] * count, columns)
                recipe = component_visual_recipe("SecondaryBody", size=size, variant=variant)
                text = recipe.get("parts", {}).get("text", {}).get("styles", {})
                root = recipe.get("parts", {}).get("root", {}).get("styles", {})
                height = text.get("height", 0)
                gap = root.get("itemMargin", 0)
                options.append({
                    "component": "SecondaryBody",
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
    return options


def composition_region_capacity(
    size: str, layout: str, variant: int, path: list[int],
) -> dict[str, Any] | None:
    layouts = _layout_geometry(size, None)
    patterns = layouts.get(layout, [])
    if not 1 <= variant <= len(patterns):
        return None
    selected = {layout: [patterns[variant - 1]]}
    for area in _content_budgets(size, selected, 0):
        if area.get("path") == path:
            fixed_gap = None
            for rule in patterns[variant - 1]:
                if rule.get("path") == path:
                    fixed_gap = rule.get("fixedProps", {}).get("itemMargin")
            return {"width": float(area.get("innerWidth")),
                    "height": float(area.get("innerHeight")), "fixedGap": fixed_gap}
    return None


def composition_group_minimum_height(size: str, group: dict[str, Any]) -> float | None:
    """核算能够无歧义确定条数的文本组合；其它组件继续由完整合同核算。"""
    name = group.get("component")
    if name in {"SingleLineTitle", "PillButton", "CardButton", "CircleButton"}:
        recipe = component_visual_recipe(name, size=size)
        return float(recipe.get("parts", {}).get("root", {}).get("styles", {}).get("height"))
    if size == "2x2" and name in {"EmphasizedData", "EmphasisText"}:
        recipe = component_visual_recipe(name, size=size)
        parts = recipe.get("parts", {})
        main = "value" if name == "EmphasizedData" else "main"
        height = parts.get(main, {}).get("styles", {}).get("height")
        if not isinstance(height, (int, float)):
            return None
        if name == "EmphasisText" and "secondaryText" in group.get("placements", []):
            secondary = parts.get("secondary", {}).get("styles", {}).get("height")
            gap = parts.get("root", {}).get("styles", {}).get("itemMargin", 0)
            if not isinstance(secondary, (int, float)):
                return None
            height += secondary + gap
        return float(height)
    if name not in {"SecondaryBody", "TableText"}:
        return None
    indexes: set[int] = set()
    for placement in group.get("placements", []):
        match = re.match(r"items\[(\d+)\]\.", placement)
        if match is not None:
            indexes.add(int(match.group(1)))
    if not indexes or indexes != set(range(len(indexes))):
        return None
    count = len(indexes)
    if name == "TableText":
        if count not in (2, 3):
            return None
        recipe = component_visual_recipe(name, size=size, variant="compact" if count == 3 else None)
        height = recipe.get("parts", {}).get("row", {}).get("styles", {}).get("height", 0)
        gap_key = "threeRowGap" if count == 3 else "twoRowGap"
        return float(count * height + (count - 1) * recipe.get("metrics", {}).get(gap_key, 0))
    columns = group.get("columns", 2)
    lines = group.get("lines", [1] * count)
    variant = secondary_body_variant([{"maxLines": line} for line in lines], columns)
    recipe = component_visual_recipe(name, size=size, variant=variant)
    styles = recipe.get("parts", {}).get("text", {}).get("styles", {})
    line_height = styles.get("height", 0) / styles.get("maxLines", 1)
    if len(lines) != count:
        return None
    height = 0.0
    for start in range(0, count, columns):
        height += line_height * max(lines[start:start + columns])
    rows = math.ceil(count / columns)
    gap = recipe.get("parts", {}).get("root", {}).get("styles", {}).get("itemMargin", 0)
    return height + (rows - 1) * gap


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
