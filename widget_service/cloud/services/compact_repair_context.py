"""修复用合同与拓扑摘要；不承担校验、字段推断或删除授权。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from app.logger import logger

JOINT_RECOMPOSITION_INSTRUCTION = (
    "此前布局已失败，本轮把结构、容量、事实、动作和素材作为同一重组问题处理，"
    "不要因错误类别切换退回单点修补。先按全部保留事实和完整动作计算各区预算，"
    "比较不同合法承载组合；放不下的旧堆叠不能只改ID、间距或包装层。"
    "仅在合同允许且不是用户必需标题时移除装饰标题；不缩固定字号，不削减事实或动作。"
    "随后一起复查树闭合、事实唯一可见、动作参数准确与入口可达、动作图标分配和横纵容量。"
)

_BOUNDED_ITEM_COMPONENTS = {
    "SecondaryBody": (1, 6),
    "SummaryList": (2, 3),
}

_SEMANTIC_LAYOUT_NODE_PATTERN = re.compile(
    r"语义布局不符合合同：节点\s+([^：:]+)[：:]"
)
_REGION_ACTION_CONTRACTS = {
    "center": ("[content]", 0),
    "title-content": ("[title, non-Action content]", 0),
    "title-hero-support": ("[title, hero, support]", 0),
    "title-content-action": ("[title, non-Action content, PillButton Action]", 1),
    "title-hero-support-action": (
        "[title, hero, support, PillButton Action]",
        1,
    ),
    "title-two-ratios": (
        "[title, ProgressCircle, ProgressCircle, PillButton Action?]",
        1,
    ),
    "four-ratios": (
        "[ProgressCircle, ProgressCircle, ProgressCircle, ProgressCircle]",
        0,
    ),
    "four-items": (
        "[non-Action content, non-Action content, non-Action content, non-Action content]",
        0,
    ),
}


def _source_component_rows(source: str) -> dict[str, dict[str, Any]]:
    """读取失败源中的组件行；结构错误时仍保留可可靠解析的行。"""
    components: dict[str, dict[str, Any]] = {}
    for line in source.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, list) or len(row) < 3:
            continue
        component_id = row[0]
        component_type = row[1]
        props = row[2]
        if not isinstance(component_id, str) or not isinstance(component_type, str):
            continue
        if not isinstance(props, dict):
            continue
        children: list[str] = []
        if len(row) >= 4 and isinstance(row[3], list):
            for child in row[3]:
                if isinstance(child, str):
                    children.append(child)
        components[component_id] = {
            "type": component_type,
            "props": props,
            "children": children,
        }
    return components


def _contains_action(
    component_id: str,
    components: dict[str, dict[str, Any]],
    visiting: set[str],
) -> bool:
    if component_id in visiting:
        return False
    component = components.get(component_id)
    if component is None:
        return False
    props = component.get("props")
    if isinstance(props, dict) and props.get("onClick"):
        return True
    next_visiting = set(visiting)
    next_visiting.add(component_id)
    children = component.get("children")
    if not isinstance(children, list):
        return False
    for child_id in children:
        if _contains_action(child_id, components, next_visiting):
            return True
    return False


def _component_child_summary(
    component: dict[str, Any],
    components: dict[str, dict[str, Any]],
) -> str:
    children = component.get("children")
    if not isinstance(children, list):
        return "[]"
    summaries: list[str] = []
    for index, child_id in enumerate(children):
        child = components.get(child_id)
        child_type = "MISSING" if child is None else str(child.get("type") or "unknown")
        action_suffix = " Action" if _contains_action(child_id, components, set()) else ""
        summaries.append(f"{index}:{child_id}({child_type}{action_suffix})")
    return "[" + ", ".join(summaries) + "]"


def _missing_reference_guidance(components: dict[str, dict[str, Any]]) -> str | None:
    missing: list[str] = []
    referenced: set[str] = set()
    for parent_id, component in components.items():
        children = component.get("children")
        if not isinstance(children, list):
            continue
        for index, child_id in enumerate(children):
            referenced.add(child_id)
            if child_id not in components:
                missing.append(f"{parent_id}.children[{index}]={child_id}")
    if not missing:
        return None
    dangling_actions: list[str] = []
    for component_id, component in components.items():
        if component_id == "root" or component_id in referenced:
            continue
        if _contains_action(component_id, components, set()):
            dangling_actions.append(f"{component_id}({component.get('type')})")
    lines = [
        "当前失败 DSL 的可执行定位：不存在的引用为 " + ", ".join(missing) + "。",
    ]
    if dangling_actions:
        lines.append(
            "当前已定义但未接入组件树的 Action 候选为 "
            + ", ".join(dangling_actions)
            + "。"
        )
    root = components.get("root")
    root_props = root.get("props") if root is not None else None
    root_layout = root_props.get("layout") if isinstance(root_props, dict) else None
    if root_layout == "W-content-side-slots":
        lines.append(
            "W-content-side-slots 的直属角色必须是 [内容 Region, 上固定槽, 下固定槽]；"
            "动作固定槽使用 CardButton。"
        )
    lines.append(
        "修复步骤：一次性检查同一父节点的全部 children；将不存在的 ID 替换为语义对应的"
        "现有组件 ID，或补建该 ID 的完整组件行，二者只能选一；随后删除未使用的旧行，并复查"
        "所有节点从 root 可达、仅有一个父引用且角色类型正确。不要只修复首个报错引用。"
    )
    return "\n".join(lines)


def _action_role_guidance(
    target_id: str,
    components: dict[str, dict[str, Any]],
    required_action_ids: list[str],
) -> str | None:
    component = components.get(target_id)
    if component is None or component.get("type") != "Region":
        return None
    props = component.get("props")
    variant = props.get("variant") if isinstance(props, dict) else None
    contract = _REGION_ACTION_CONTRACTS.get(variant)
    if contract is None:
        return None
    expected_roles, action_capacity = contract
    children = component.get("children")
    if not isinstance(children, list):
        return None
    action_children: list[str] = []
    for child_id in children:
        if _contains_action(child_id, components, set()):
            action_children.append(child_id)
    lines = [
        f"当前失败 DSL 的可执行定位：{target_id} 是 Region(variant={variant})，"
        f"直属 children={_component_child_summary(component, components)}。",
        f"该变体的有序角色是 {expected_roles}，最多容纳 {action_capacity} 个 Action 子树；"
        f"当前检测到 {len(action_children)} 个：{action_children}。",
    ]
    if required_action_ids:
        lines.append(
            "已接受 Plan 要求整卡保留的 Action 为 "
            f"{required_action_ids}；局部修复不得通过遗漏其余 Action 获得通过。"
        )
    single_action_needs_action_variant = (
        action_capacity == 0 and len(action_children) == 1
    )
    if single_action_needs_action_variant:
        lines.append(
            "当前变体没有动作角色。若该 Region 只承载这一个 Action，应切换到具有一个末尾"
            "动作角色的合法变体，并补齐其要求的非 Action 内容角色；整卡其余必需 Action 必须"
            "放入兄弟 Region 或父布局的独立动作槽，不能继续塞入本 Region 的 content。"
        )
    elif len(action_children) > action_capacity:
        lines.append(
            "当前 Region 无法同时容纳这些 Action。不要把 PillButton 或含 onClick 的 Group 放入"
            " content/hero/support 角色，也不要只改 variant 名称；必须提升到共同父布局，将每个"
            " Action 分配到独立合法动作槽，或分配到不同 Region 的末尾动作角色。"
        )
    elif action_children:
        lines.append(
            "将唯一 Action 子树移动到该变体允许的末尾动作角色；其余 content/hero/support"
            " 必须换成不含 onClick 的业务展示组件。若当前变体没有动作角色，改用动作版变体并"
            "同时补齐全部非 Action 角色。"
        )
    lines.append(
        "修改后逐项复查：children 数量、顺序、每个角色的组件类型、Action 总数及可达性；"
        "保留原 Action 的 call、args、标签和素材，不复制或删除 Action。"
    )
    return "\n".join(lines)


def _required_plan_action_ids(compact_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(compact_plan, dict):
        return []
    facts = compact_plan.get("info_required")
    if not isinstance(facts, list):
        return []
    action_ids: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        action_id = fact.get("actionId")
        if isinstance(action_id, str) and action_id and action_id not in action_ids:
            action_ids.append(action_id)
    return action_ids


def semantic_layout_repair_guidance(
    source: str,
    quality_errors: list[dict[str, Any]],
    compact_plan: dict[str, Any] | None = None,
) -> str | None:
    """从失败 DSL 提取可执行的语义布局修复步骤，不改变校验或删除权限。"""
    messages = [str(issue.get("message") or "") for issue in quality_errors]
    semantic_messages = [
        message for message in messages if "语义布局不符合合同" in message
    ]
    if not semantic_messages:
        return None
    components = _source_component_rows(source)
    if not components:
        return None
    paragraphs: list[str] = []
    if any("引用了不存在的组件" in message for message in semantic_messages):
        missing_guidance = _missing_reference_guidance(components)
        if missing_guidance is not None:
            paragraphs.append(missing_guidance)
    target_ids: list[str] = []
    for message in semantic_messages:
        match = _SEMANTIC_LAYOUT_NODE_PATTERN.search(message)
        if match is None:
            continue
        target_id = match.group(1).strip()
        if target_id not in target_ids:
            target_ids.append(target_id)
    has_action_role_error = any(
        "Action 必须放在所选 Region 的底部动作角色中" in message
        for message in semantic_messages
    )
    if has_action_role_error:
        required_action_ids = _required_plan_action_ids(compact_plan)
        for target_id in target_ids:
            action_guidance = _action_role_guidance(
                target_id,
                components,
                required_action_ids,
            )
            if action_guidance is not None:
                paragraphs.append(action_guidance)
    if not paragraphs:
        return None
    return "\n\n".join(paragraphs)


def _normalized_visible_text(value: str) -> str:
    """忽略展示空白，保留业务字符用于 Plan 事实对应。"""
    return re.sub(r"\s+", "", value).strip().lower()


def _value_signals(value: Any) -> tuple[set[str], set[str]]:
    """提取一项展示值中的路径和静态文案，不推断运行时表达式结果。"""
    paths: set[str] = set()
    literals: set[str] = set()
    if isinstance(value, str):
        paths.update(re.findall(r"\$\{(?P<path>/[^}\s]+)\}", value))
        normalized = _normalized_visible_text(value)
        if normalized:
            literals.add(normalized)
        return paths, literals
    if isinstance(value, list):
        for item in value:
            item_paths, item_literals = _value_signals(item)
            paths.update(item_paths)
            literals.update(item_literals)
        return paths, literals
    if not isinstance(value, dict):
        return paths, literals
    path = value.get("path")
    if isinstance(path, str) and path:
        paths.add(path)
    for nested in value.values():
        item_paths, item_literals = _value_signals(nested)
        paths.update(item_paths)
        literals.update(item_literals)
    return paths, literals


def _matching_plan_facts(item: Any, plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    """把当前条目与可证明对应的 Plan 事实关联，避免猜测模糊语义。"""
    if not isinstance(plan, dict):
        return []
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return []
    paths, literals = _value_signals(item)
    matched: list[dict[str, Any]] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or "actionId" in fact:
            continue
        data_id = fact.get("dataId")
        path_matches = isinstance(data_id, str) and data_id in paths
        fact_texts: list[str] = []
        for key in ("requirement", "text"):
            value = fact.get(key)
            if isinstance(value, str) and value.strip():
                fact_texts.append(_normalized_visible_text(value))
        literal_matches = False
        for literal in literals:
            if literal_matches:
                break
            for fact_text in fact_texts:
                if not literal or not fact_text:
                    continue
                same_text = literal == fact_text
                overlapping_text = literal in fact_text or fact_text in literal
                if same_text or overlapping_text:
                    literal_matches = True
                    break
        if not path_matches and not literal_matches:
            continue
        matched.append(
            {
                "factIndex": index,
                "requirement": copy.deepcopy(fact.get("requirement")),
                "priority": str(fact.get("priority") or "must"),
            }
        )
    return matched


def _compact_diagnostics(quality_errors: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    """兼容直接诊断与 issue.promptContext 中的结构化诊断。"""
    diagnostics: list[dict[str, Any]] = []
    for issue in quality_errors:
        if not isinstance(issue, dict):
            continue
        if isinstance(issue.get("actual"), dict):
            diagnostics.append(issue)
        nested = issue.get("compactDiagnostics")
        if not isinstance(nested, list):
            continue
        for diagnostic in nested:
            if isinstance(diagnostic, dict):
                diagnostics.append(diagnostic)
    return diagnostics


def _height_capacity_evidence(
    quality_errors: list[Any] | tuple[Any, ...],
) -> list[dict[str, Any]]:
    evidence_by_component: dict[str, dict[str, Any]] = {}
    for diagnostic in _compact_diagnostics(quality_errors):
        if diagnostic.get("code") != "COMPACT_LAYOUT_HEIGHT_OVERFLOW":
            continue
        actual = diagnostic.get("actual")
        fits = actual.get("secondaryBodyFits") if isinstance(actual, dict) else None
        if not isinstance(fits, list):
            continue
        for fit in fits:
            if not isinstance(fit, dict):
                continue
            component_id = fit.get("componentId")
            retained_count = fit.get("maxRetainedRowCount")
            if not isinstance(component_id, str) or not isinstance(retained_count, int):
                continue
            previous = evidence_by_component.get(component_id)
            previous_count = None if previous is None else previous.get("maxRetainedRowCount")
            if isinstance(previous_count, int) and previous_count <= retained_count:
                continue
            evidence_by_component[component_id] = fit
    return list(evidence_by_component.values())


def _indexed_items(
    items: list[Any],
    indexes: Any,
    plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not isinstance(indexes, list):
        return payloads
    for index in indexes:
        if isinstance(index, bool) or not isinstance(index, int):
            continue
        if not 0 <= index < len(items):
            continue
        item = items[index]
        payloads.append(
            {
                "itemIndex": index,
                "value": copy.deepcopy(item),
                "planFacts": _matching_plan_facts(item, plan),
            }
        )
    return payloads


def _secondary_body_height_contexts(
    components: dict[str, dict[str, Any]],
    quality_errors: list[Any] | tuple[Any, ...],
    plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for evidence in _height_capacity_evidence(quality_errors):
        component_id = evidence.get("componentId")
        component = components.get(component_id)
        if component is None or component.get("type") != "SecondaryBody":
            continue
        props = component.get("props")
        items = props.get("items") if isinstance(props, dict) else None
        if not isinstance(items, list):
            continue
        directly_fits = _indexed_items(
            items,
            evidence.get("directlyFitsItemIndexes"),
            plan,
        )
        does_not_fit = _indexed_items(
            items,
            evidence.get("doesNotFitItemIndexes"),
            plan,
        )
        if not does_not_fit:
            continue
        overflow_fact_indexes: set[int] = set()
        for item in does_not_fit:
            for fact in item["planFacts"]:
                fact_index = fact.get("factIndex")
                if isinstance(fact_index, int) and not isinstance(fact_index, bool):
                    overflow_fact_indexes.add(fact_index)
        contexts.append(
            {
                "componentId": component_id,
                "componentType": "SecondaryBody",
                "actualItemCount": len(items),
                "actualRowCount": evidence.get("actualRowCount"),
                "maxRetainedRowCount": evidence.get("maxRetainedRowCount"),
                "effectiveColumnCount": evidence.get("effectiveColumnCount"),
                "rowHeights": copy.deepcopy(evidence.get("rowHeights")),
                "rowSpacing": evidence.get("rowSpacing"),
                "parentId": evidence.get("parentId"),
                "parentAvailableHeight": evidence.get("parentAvailableHeight"),
                "directlyFits": directly_fits,
                "doesNotFit": does_not_fit,
                "overflowItemCount": len(does_not_fit),
                "overflowFactCount": len(overflow_fact_indexes),
                "scope": "currentComponentItemsOnly",
                "instruction": (
                    "父区域剩余高度结合当前列分组、展开后行高和行间距，只能保留 "
                    "maxRetainedRowCount 行；doesNotFit 是当前组件中无法容纳的条目。"
                    "该切分不是省略授权；只有 repairStrategy.optionalDrop 或 "
                    "approvedOmissions 明确列出的非 Action 事实才允许删除。"
                ),
            }
        )
    return contexts


def bounded_component_capacity_contexts(
    source: str,
    quality_errors: list[Any] | tuple[Any, ...],
    plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """生成条目容量修复证据；不改变校验或授权省略事实。"""
    messages: list[str] = []
    for issue in quality_errors:
        if isinstance(issue, dict):
            messages.append(str(issue.get("message") or ""))
        else:
            messages.append(str(issue))
    message_text = "\n".join(messages).lower()
    components = _source_component_rows(source)
    contexts = _secondary_body_height_contexts(components, quality_errors, plan)
    for component_id, component in components.items():
        component_type = component.get("type")
        props = component.get("props")
        if not isinstance(component_type, str):
            continue
        limits = _BOUNDED_ITEM_COMPONENTS.get(component_type)
        if limits is None or not isinstance(props, dict):
            continue
        items = props.get("items")
        minimum, maximum = limits
        if not isinstance(items, list) or len(items) <= maximum:
            continue
        marker = f"{component_id}: {component_type}.items requires".lower()
        if marker not in message_text:
            continue
        item_payloads: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            item_payloads.append(
                {
                    "itemIndex": index,
                    "value": copy.deepcopy(item),
                    "planFacts": _matching_plan_facts(item, plan),
                }
            )
        contexts.append(
            {
                "componentId": component_id,
                "componentType": component_type,
                "actualItemCount": len(items),
                "allowedItemCount": {"min": minimum, "max": maximum},
                "directlyFits": item_payloads[:maximum],
                "doesNotFit": item_payloads[maximum:],
                "overflowItemCount": len(items) - maximum,
                "scope": "currentComponentOnly",
                "instruction": (
                    "当前组件按现有顺序最多直接承载 allowedItemCount.max 项；"
                    "doesNotFit 必须改由其它合法布局或组件承载。该切分只说明当前组件容量，"
                    "不是省略授权；只有 repairStrategy.optionalDrop 或 approvedOmissions "
                    "明确列出的非 Action 事实才允许删除。"
                ),
            }
        )
    return contexts


_STATIC_FIELD_STYLES = {
    "SingleLineList": {"text": "singleText", "assist": "singleAssist"},
    "TextList": {"primaryText": "listPrimary", "secondaryText": "listSecondary",
                 "value": "listValue"},
    "ComparisonGroup": {"primaryText": "comparisonPrimary", "secondaryText": "comparisonSecondary"},
    "EmphasisText": {"mainText": "emphasis", "secondaryText": "emphasisSecondary"},
    "SingleLineTitle": {"title": "header"},
}


def _static_width_targets(
    component_id: str, component: dict[str, Any], message: str,
) -> list[tuple[int | None, str]]:
    """原生容量文案须对应当前字段，并以同合同重新确认超宽。"""
    from services.static_text_capacity import measure_text, text_spec

    styles = _STATIC_FIELD_STYLES.get(component.get("type"), {})
    props = component.get("props", {})
    pattern = (
        r"(?<![\w./-])" + re.escape(component_id)
        + r"\.(?:item(\d+)_)?([A-Za-z]+) 完整文字需要 "
        r"(\d+) 行，([\d.]+)vp 区域仅允许 (\d+) 行"
    )
    result = []
    if "COMPACT_STATIC_TEXT_CAPACITY:" not in message:
        return result
    for match in re.finditer(pattern, message):
        item_number, field, lines, width, maximum = match.groups()
        style = styles.get(field)
        if style is None or int(lines) <= int(maximum):
            continue
        item_index = int(item_number) if item_number is not None else None
        values = props
        if item_index is not None:
            items = props.get("items")
            if not isinstance(items, list) or not 0 <= item_index < len(items):
                continue
            values = items[item_index]
        if not isinstance(values, dict):
            continue
        value = values.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        if "{{" in value or "${" in value:
            continue
        try:
            capacity = measure_text(value, float(width), text_spec(style))
        except ValueError:
            continue
        if not capacity.fits:
            result.append((item_index, field))
    return result


def _static_excess_items(
    component_id: str, component: dict[str, Any], root: dict[str, Any], message: str,
) -> list[int]:
    """仅识别当前源已证明的项数上界冲突，不把下界或空字段算容量。"""
    kind = component.get("type")
    items = component.get("props", {}).get("items")
    if component_id != "body" or not isinstance(items, list):
        return []
    if component_id not in root.get("children", []):
        return []
    has_header = "header" in root.get("children", [])
    maximum = len(items)
    if kind == "TextList":
        if has_header and "TextList 含标题区时最多两项" in message:
            maximum = 2
        elif "TextList.items 必须为2–3项" in message:
            maximum = 3
    elif kind == "ComparisonGroup":
        if has_header and "ComparisonGroup 四项宫格占满正文区" in message:
            maximum = 3
    return list(range(len(items))) if len(items) > maximum else []


def static_component_capacity_contexts(
    source: str, quality_errors: list[dict[str, Any]], plan: dict[str, Any] | None,
    approved_indexes: tuple[int, ...] = (),
) -> list[dict[str, Any]]:
    """静态只给当前错误字段的所属事实生成证据；证据本身不授权删除。"""
    from services.card_validation.compact_validation.semantic.static_content import (
        static_capacity_fact_indexes,
    )

    if not isinstance(plan, dict):
        return []
    components = _source_component_rows(source)
    root = components.get("root", {})
    if root.get("type") != "Layout":
        return []
    message = "\n".join(str(issue.get("message") or "") for issue in quality_errors)
    result = []
    for identifier in root.get("children", []):
        component = components.get(identifier)
        if component is None:
            continue
        targets = _static_width_targets(identifier, component, message)
        excess_items = _static_excess_items(identifier, component, root, message)
        for index in excess_items:
            targets.append((index, None))
        if not targets:
            continue
        overflow = []
        for item_index, property_name in dict.fromkeys(targets):
            try:
                indexes = static_capacity_fact_indexes(
                    source, plan, identifier, item_index, property_name, approved_indexes,
                )
            except (TypeError, ValueError):
                indexes = ()
            overflow.append({
                "itemIndex": item_index, "property": property_name,
                "planFacts": [{"factIndex": index} for index in indexes],
            })
        result.append({
            "componentId": identifier, "componentType": component.get("type"),
            "doesNotFit": overflow, "scope": "currentStaticField",
            "instruction": "只核对当前字段所属事实；证据不授权删除整组或其它条目。",
        })
    return result


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
