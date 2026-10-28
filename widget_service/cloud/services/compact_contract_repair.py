"""组件合同修复候选；依据本轮 Plan/TaskSpec，不调用模型或改写注册合同。"""

import json
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

from services.compact_component_semantics import CORE_INFORMATION_COMPONENT_TYPES
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    _json_pointer_value,
    build_compact_data_model,
    parse_compact_dsl_rows,
)
from services.compact_outer_recomposition import _serialize, _unique_id
from services.generation_pipeline import DslProcessingContext, DslProcessingResult

CONTRACT_RULES = {
    "known-component": "已知正文组件纠正",
    "primary-content": "辅助信息主体合同",
    "action-slot": "按钮角色纠正",
    "asset-reference": "登记素材引用补齐",
    "plan-fact": "明确授权事实补齐",
    "fixed-slot": "固定信息槽归位",
    "numeric-label": "数值文字标签补齐",
    "event-target": "唯一动作候选参数纠正",
}


def _changed(rows: tuple, changed: ComponentRow, extra: tuple = ()) -> str:
    result = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_id == changed.component_id:
            row = changed
        result.append(row)
    result.extend(extra)
    return _serialize(result)


def _known_component(result: DslProcessingResult) -> Iterator[tuple[str, str]]:
    if not any("unsupported component type ContentBlock." in i.message for i in result.errors):
        return
    try:
        rows = [json.loads(line) for line in result.source_dsl.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 3:
            continue
        if row[1] != "ContentBlock" or not isinstance(row[2], dict):
            continue
        props = row[2]
        if set(props) != {"body"}:
            continue
        body = props.get("body")
        if not isinstance(body, str) or not body.strip():
            continue
        changed = list(rows)
        changed[index] = [row[0], "EmphasisText", {"mainText": body}]
        source = "\n".join(json.dumps(item, ensure_ascii=False) for item in changed)
        yield "known-component", source


def _primary_content(rows: tuple, nodes: dict, result: DslProcessingResult) -> Iterator[str]:
    if not any("SecondaryBody is auxiliary" in issue.message for issue in result.errors):
        return
    if any(row.component_type in CORE_INFORMATION_COMPONENT_TYPES for row in nodes.values()):
        return
    for row in nodes.values():
        if row.component_type != "SecondaryBody" or row.children:
            continue
        if set(row.props) - {"items", "columns", "fontSize", "fontColor"}:
            continue
        items = row.props.get("items")
        if not isinstance(items, list) or len(items) not in {2, 4}:
            continue
        if row.props.get("fontSize", 12) != 12:
            continue
        if not all(isinstance(item, dict) and set(item) == {"label", "value"} for item in items):
            continue
        props = {"items": items, "fontSize": 12}
        if "fontColor" in row.props:
            props["fontColor"] = row.props.get("fontColor")
        if len(items) == 2:
            yield _changed(rows, replace(row, component_type="TableText", props=props))
            continue
        used = set(nodes)
        left_id = _unique_id(row.component_id + "_table_left", used)
        used.add(left_id)
        right_id = _unique_id(row.component_id + "_table_right", used)
        left = ComponentRow(left_id, "TableText", {**props, "items": items[:2]}, ())
        right = ComponentRow(right_id, "TableText", {**props, "items": items[2:]}, ())
        for variant in ("peer-pair", "hero-support"):
            group = replace(
                row,
                component_type="Group",
                props={"variant": variant},
                children=(left_id, right_id),
            )
            yield _changed(rows, group, (left, right))


def _action_slots(nodes: dict) -> Iterator[ComponentRow]:
    for parent in nodes.values():
        layout = parent.props.get("layout")
        pill_layouts = {
            "S-title-content-action",
            "S-title-primary-secondary-action",
            "S-title-dual-column-action",
        }
        required = None
        if parent.component_type == "Layout" and layout in pill_layouts:
            required = "PillButton"
        if parent.component_type == "Region":
            if parent.props.get("variant") in {"title-content-action", "title-hero-support-action"}:
                required = "PillButton"
        if not required or not parent.children:
            continue
        action = nodes.get(parent.children[-1])
        if action is None or action.component_type not in {"CardButton", "CircleButton"}:
            continue
        if not action.props.get("onClick") or not action.props.get("label"):
            continue
        if set(action.props) - {"label", "icon", "onClick", "fontColor", "fillColor"}:
            continue
        yield replace(action, component_type=required)


def _asset_references(nodes: dict, context: DslProcessingContext) -> Iterator[ComponentRow]:
    assets = {}
    for asset in context.task_spec.get("assetCandidates", []):
        identifier, source = asset.get("id"), asset.get("src")
        if isinstance(identifier, str) and isinstance(source, str):
            assets.setdefault(identifier, set()).add(source)
    title_asset = (context.compact_plan or {}).get("assetAssignments", {}).get("title", {})
    title_id = title_asset.get("assetId") if isinstance(title_asset, dict) else None
    titles = [row for row in nodes.values() if row.component_type == "SingleLineTitle"]
    for row in nodes.values():
        props = dict(row.props)
        for key in ("icon", "src"):
            value = props.get(key)
            matches = assets.get(value, set()) if isinstance(value, str) else set()
            if len(matches) == 1:
                props[key] = next(iter(matches))
        if len(titles) == 1 and row == titles[0] and "icon" not in props:
            matches = assets.get(title_id, set())
            if len(matches) == 1:
                props["icon"] = next(iter(matches))
        if props != row.props:
            yield replace(row, props=props)


def _missing_fact(
    rows: tuple, nodes: dict, result: DslProcessingResult, context: DslProcessingContext
) -> Iterator[str]:
    facts = (context.compact_plan or {}).get("info_required", [])
    missing = []
    for fact in facts:
        path = fact.get("dataId")
        if not isinstance(path, str):
            continue
        for issue in result.errors:
            if "Plan fact is missing from visible DSL:" in issue.message:
                if f"({path})." in issue.message:
                    missing.append(fact)
                    break
    if not 1 <= len(missing) <= 2:
        return
    data_rows = [row for row in rows if not isinstance(row, ComponentRow)]
    data = build_compact_data_model(data_rows)
    additions = []
    for fact in missing:
        path = fact.get("dataId")
        found, schema = _json_pointer_value(context.task_spec.get("dataModelSchema", {}), path)
        initialized, initial = _json_pointer_value(data, path)
        if not found or not initialized or not isinstance(schema, dict):
            return
        if schema.get("type") == "string" and isinstance(initial, str):
            value = {"path": path}
        elif schema.get("type") == "boolean" and isinstance(initial, bool):
            value = f"{{{{ ${{{path}}} ? '是' : '否' }}}}"
        else:
            return
        requirement = fact.get("requirement")
        if not isinstance(requirement, str) or not requirement.strip():
            return
        additions.append({"label": requirement, "value": value})
    for host in nodes.values():
        if host.component_type != "SecondaryBody":
            continue
        items = host.props.get("items")
        if isinstance(items, list) and len(items) + len(additions) <= 6:
            changed = replace(host, props={**host.props, "items": [*items, *additions]})
            yield _changed(rows, changed)
    if len(missing) != 1:
        return
    fact = missing[0]
    path = fact.get("dataId")
    found, schema = _json_pointer_value(context.task_spec.get("dataModelSchema", {}), path)
    if not found or not isinstance(schema, dict) or schema.get("type") != "string":
        return
    if "SingleLineTitle" not in fact.get("componentHints", []):
        return
    if any(row.component_type == "SingleLineTitle" for row in nodes.values()):
        return
    root = nodes.get("root")
    if root is None or root.props.get("layout") != "S-content-dual-action":
        return
    host = nodes.get(root.children[0]) if len(root.children) == 3 else None
    if host is None or host.component_type not in {"SecondaryBody", "Group"}:
        return
    body_id = _unique_id(host.component_id + "_body", set(nodes))
    title_id = _unique_id(host.component_id + "_fact", set(nodes) | {body_id})
    body = replace(host, component_id=body_id)
    title = ComponentRow(title_id, "SingleLineTitle", {"title": {"path": path}}, ())
    group = replace(
        host,
        component_type="Group",
        props={"variant": "hero-support"},
        children=(title_id, body_id),
    )
    yield _changed(rows, group, (title, body))


def _fixed_slot(rows: tuple, nodes: dict) -> Iterator[str]:
    root = nodes.get("root")
    if root is None or root.props.get("layout") != "W-content-side-slots":
        return
    if len(root.children) != 3:
        return
    content = nodes.get(root.children[0])
    if content is None or content.component_type != "Region":
        return
    if content.props != {"variant": "title-hero-support"} or len(content.children) != 3:
        return
    title_id, primary_id, support_id = content.children
    primary = nodes.get(primary_id)
    if primary is None or primary.component_type != "InfoBlock":
        return
    group = replace(
        content,
        component_type="Group",
        props={"variant": "label-value"},
        children=(title_id, support_id),
    )
    props = dict(root.props)
    props["layout"] = "W-four-slots"
    props.pop("orientation", None)
    changed_root = replace(
        root, props=props, children=(content.component_id, primary_id, *root.children[1:])
    )
    changed = []
    for row in rows:
        if row == content:
            row = group
        changed.append(row)
    yield _changed(tuple(changed), changed_root)


def _numeric_label(nodes: dict, context: DslProcessingContext) -> Iterator[ComponentRow]:
    title = context.card_spec.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 8:
        return
    for row in nodes.values():
        if row.component_type != "DataDisplay" or row.props.get("label"):
            continue
        value = row.props.get("value")
        if not isinstance(value, dict) or set(value) != {"path"}:
            continue
        if not isinstance(value.get("path"), str):
            continue
        found, schema = _json_pointer_value(
            context.task_spec.get("dataModelSchema", {}), value.get("path")
        )
        if not found or not isinstance(schema, dict):
            continue
        if schema.get("type") not in {"number", "integer"}:
            continue
        icon = row.props.get("icon")
        if icon is not None:
            holders = [node for node in nodes.values() if node.component_type == "SingleLineTitle"]
            if not any(node.props.get("icon") == icon for node in holders):
                continue
        props = {**row.props, "label": title}
        props.pop("icon", None)
        yield replace(row, props=props)


def _event_target(nodes: dict, context: DslProcessingContext) -> Iterator[ComponentRow]:
    facts = (context.compact_plan or {}).get("info_required", [])
    action_ids = {fact.get("actionId") for fact in facts if fact.get("actionId")}
    buttons = []
    for row in nodes.values():
        if row.component_type in {"PillButton", "CircleButton", "CardButton"}:
            if row.props.get("onClick"):
                buttons.append(row)
    if len(action_ids) != 1 or len(buttons) != 1:
        return
    expected = {}
    for event in context.task_spec.get("eventCandidates", []):
        if event.get("id") not in action_ids:
            continue
        handler = {"call": event.get("call"), "args": event.get("args")}
        if not isinstance(handler["call"], str) or not isinstance(handler["args"], dict):
            continue
        expected[json.dumps(handler, sort_keys=True)] = handler
    if len(expected) != 1:
        return
    handler = next(iter(expected.values()))
    button = buttons[0]
    actual = button.props.get("onClick")
    if not isinstance(actual, list) or len(actual) != 1 or not isinstance(actual[0], dict):
        return
    old_args = actual[0].get("args")
    if not isinstance(old_args, dict) or actual[0].get("call") != handler.get("call"):
        return
    if old_args.get("intentName") != handler["args"].get("intentName"):
        return
    if actual[0] != handler:
        yield replace(button, props={**button.props, "onClick": [handler]})


def contract_candidates(
    result: DslProcessingResult, settings: Any, context: DslProcessingContext | None
) -> Iterator[tuple[str, str]]:
    if context is None or not result.errors:
        return
    if settings.enable_compact_known_component_repair:
        yield from _known_component(result)
    try:
        rows = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    except CompactDslConversionError:
        return
    nodes = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            nodes[row.component_id] = row
    if settings.enable_compact_primary_content_repair:
        for source in _primary_content(rows, nodes, result):
            yield "primary-content", source
    if settings.enable_compact_plan_fact_repair:
        for source in _missing_fact(rows, nodes, result, context):
            yield "plan-fact", source
    if settings.enable_compact_fixed_slot_repair:
        for source in _fixed_slot(rows, nodes):
            yield "fixed-slot", source
    groups = (
        (settings.enable_compact_action_slot_repair, "action-slot", _action_slots(nodes)),
        (
            settings.enable_compact_asset_reference_repair,
            "asset-reference",
            _asset_references(nodes, context),
        ),
        (
            settings.enable_compact_numeric_label_repair,
            "numeric-label",
            _numeric_label(nodes, context),
        ),
        (
            settings.enable_compact_event_target_repair,
            "event-target",
            _event_target(nodes, context),
        ),
    )
    for enabled, rule, candidates in groups:
        if enabled:
            for changed in candidates:
                yield rule, _changed(rows, changed)
