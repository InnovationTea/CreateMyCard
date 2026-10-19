"""从定稿内容提取选择主题所需语义，不向主题模型发送 DSL 或绘制参数。"""

from collections import Counter
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_plan import _compact_visible_state

_VISIBLE_KEYS = frozenset({
    "content", "displayValue", "items", "label", "location", "mainText", "primaryText",
    "secondaryInfo", "secondaryLabel", "secondaryText", "supportingText", "time", "title",
    "total", "unit", "value", "externalText", "text",
})
_CONTAINERS = frozenset({"Layout", "Region", "Group", "Row", "Column", "Stack"})
_GROUPS = frozenset({"Region", "Group"})


def _visible_value(value: Any) -> Any:
    result: Any = None
    if isinstance(value, dict):
        if set(value) == {"path"}:
            result = value
        else:
            result = {}
            for key, item in value.items():
                if key in _VISIBLE_KEYS:
                    result[key] = _visible_value(item)
    elif isinstance(value, list):
        result = [_visible_value(item) for item in value]
    elif isinstance(value, (str, int, float, bool)):
        result = str(value)
    return result


def _content_summary(row: ComponentRow) -> dict:
    props = {}
    for key, value in row.props.items():
        if key in _VISIBLE_KEYS:
            props[key] = _visible_value(value)
    state = _compact_visible_state([ComponentRow(row.component_id, row.component_type, props)])
    texts = []
    for text in state.literals:
        if text and not text.startswith("resources/"):
            texts.append(text)
    return {"contentType": row.component_type, "texts": texts, "dataPaths": sorted(state.paths),
            "interactive": bool(row.props.get("onClick"))}


def _group_for(identity: str, parents: dict, by_id: dict) -> str:
    visited = set()
    group = "content"
    current = parents.get(identity)
    while current and current not in visited:
        visited.add(current)
        ancestor = by_id.get(current)
        if ancestor is None:
            break
        if ancestor.component_type in _GROUPS:
            group = current
            break
        current = parents.get(current)
    return group


def _summarize(rows: list[ComponentRow], *, source_kind: str) -> dict:
    by_id = {row.component_id: row for row in rows}
    parents = {}
    for row in rows:
        for child in row.children:
            parents[child] = row.component_id
    groups = {}
    layouts = []
    kinds = Counter()
    actions = 0
    for row in rows:
        if row.props.get("onClick"):
            actions += 1
        if row.component_type == "Layout":
            layouts.append(row.props.get("layout"))
        if row.component_type in _CONTAINERS:
            continue
        kinds[row.component_type] += 1
        content = _content_summary(row)
        if not content.get("texts") and not content.get("dataPaths"):
            continue
        group_id = _group_for(row.component_id, parents, by_id)
        group = groups.setdefault(group_id, {"contents": []})
        ancestor = by_id.get(group_id)
        if ancestor is not None:
            group["type"] = ancestor.component_type
            for key in ("role", "variant", "align", "alignItems"):
                if key in ancestor.props:
                    group[key] = ancestor.props.get(key)
        group.get("contents", []).append(content)
    return {"complete": bool(rows), "source": source_kind, "layoutTypes": layouts,
            "contentGroups": list(groups.values()), "componentCounts": dict(kinds),
            "actionCount": actions}


def layout_summary(final_layout: str | None, nodes: list[dict]) -> dict:
    rows = []
    parse_failed = False
    if final_layout:
        try:
            rows = [row for row in parse_compact_dsl_rows(final_layout, expand_layouts=False)
                    if isinstance(row, ComponentRow)]
        except ValueError:
            parse_failed = True
    source_kind = "compact-semantics"
    if not rows:
        source_kind = "expanded-visible-content"
        for node in nodes:
            props = {key: value for key, value in node.items() if key in _VISIBLE_KEYS}
            if node.get("onClick"):
                props["onClick"] = True
            rows.append(ComponentRow(str(node.get("id", "")), str(node.get("component", "")),
                                     props, tuple(node.get("children", []))))
    result = _summarize(rows, source_kind=source_kind)
    if parse_failed:
        result["compactSummaryUnavailable"] = True
    return result


def matches_subjectless_layout(final_layout: str | None, requirement: dict) -> bool:
    """仅认可定稿的左内容右双槽骨架，不从请求文字推断布局。"""
    if not final_layout:
        return False
    try:
        rows = parse_compact_dsl_rows(final_layout, expand_layouts=False)
    except ValueError:
        return False
    by_id = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            by_id[row.component_id] = row
    root = by_id.get("root")
    if root is None or root.component_type != "Layout" or len(root.children) != 3:
        return False
    if root.props.get("layout") != requirement.get("layout"):
        return False
    if root.props.get("orientation", "content-left") != requirement.get("orientation"):
        return False
    expected_types = ({"Region"}, {"InfoBlock", "CardButton"}, {"InfoBlock", "CardButton"})
    for identity, allowed in zip(root.children, expected_types, strict=True):
        child = by_id.get(identity)
        if child is None or child.component_type not in allowed:
            return False
        if child.component_type == "InfoBlock" and child.props.get("variant") != "slot":
            return False
    return True


def theme_description(theme: dict) -> dict:
    """白名单字段投影；颜色、图片地址、构图坐标和完整配置绝不进入模型输入。"""
    result = {"themeId": theme.get("id"), "type": theme.get("kind"),
              "name": theme.get("name"), "description": theme.get("description")}
    for key in ("business", "family", "sizes", "composition"):
        if key in theme:
            result[key] = theme.get(key)
    return result
