"""小卡十种语义布局及十四个原示例的完整转换回归。"""

import json
import re
from pathlib import Path

import pytest

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
    serialize_compact_dsl_source,
)
from services.compact_layout_runtime import match_compact_layout
from services.compact_semantic_layout import SMALL_CHILD_ROLES

SOURCE = Path(__file__).parents[1] / (
    "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x2.md"
)
LEGACY = json.loads((Path(__file__).parent / (
    "fixtures/compact_semantic_2x2_legacy.json"
)).read_text(encoding="utf-8"))


def _source(rows: list[list]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _leaf(identifier: str, kind: str) -> list:
    props = {"mainText": "正常", "fontSize": 18}
    if kind == "SingleLineTitle":
        props = {"title": "设备", "fontSize": 12}
    elif kind == "SecondaryBody":
        props = {"items": [{"value": "已更新"}], "fontSize": 14}
    elif kind == "DataDisplay":
        props = {"label": "剩余", "value": 7, "supportingText": "天", "fontSize": 48}
    elif kind == "InfoBlock":
        props = {"primaryText": "设备", "secondaryText": "在线",
                 "backgroundColor": "#CCFFFFFF"}
    elif kind == "ProgressCircle":
        props = {"externalText": 68, "icon": "resources/base/media/phone_fill.svg",
                 "fillColor": "#991F4799", "color": "#FF1F4799",
                 "backgroundColor": "#331F4799", "accessibility": {"label": identifier}}
    elif kind in {"PillButton", "CircleButton", "CardButton"}:
        props = {"onClick": [{"call": "open", "args": {}}]}
        if kind in {"PillButton", "CardButton"}:
            props["label"] = "查看"
        else:
            props.update(icon="resources/base/media/bluetooth_fill.svg",
                         accessibility={"label": "设置"})
    return [identifier, kind, props]


def _layout_source(layout: str, variant: str = "standard", action: bool = False) -> str:
    kinds = {
        "S-center": ["DataDisplay"],
        "S-title-content": ["SingleLineTitle", "EmphasisText"],
        "S-title-dual-content": ["SingleLineTitle", "EmphasisText", "SecondaryBody"],
        "S-quad-content": ["ProgressCircle"] * 4,
        "S-title-content-action": ["SingleLineTitle", "EmphasisText", "PillButton"],
        "S-title-primary-secondary-action": [
            "SingleLineTitle", "EmphasisText", "SecondaryBody", "PillButton",
        ],
        "S-title-dual-column-action": ["SingleLineTitle", "ProgressCircle", "ProgressCircle"],
        "S-title-anchor": ["SingleLineTitle", "EmphasisText", "EmphasisText", "CircleButton"],
        "S-content-dual-action": ["EmphasisText", "CardButton", "CardButton"],
        "S-dual-info": ["InfoBlock", "InfoBlock"],
    }.get(layout)
    assert kinds is not None
    if variant == "stacked-info":
        kinds = ["SingleLineTitle", "InfoBlock", "InfoBlock"]
    if layout == "S-content-dual-action" and variant == "actions-only":
        kinds = ["CardButton", "CardButton"]
    if action:
        kinds.append("PillButton")
    leaves = []
    for index, kind in enumerate(kinds):
        leaf = _leaf(f"item{index}", kind)
        if variant == "stacked-info" and kind == "InfoBlock":
            leaf[2]["variant"] = "stacked"
        leaves.append(leaf)
    children = [row[0] for row in leaves]
    return _source([["root", "Layout", {"layout": layout, "variant": variant}, children],
                    *leaves])


@pytest.mark.parametrize("layout", SMALL_CHILD_ROLES)
def test_small_semantic_layout_matches_registered_contract_and_converts(layout: str) -> None:
    source = _layout_source(layout)
    rows = parse_compact_dsl_rows(source, size="2x2")
    components = [row for row in rows if isinstance(row, ComponentRow)]
    assert match_compact_layout(components, size="2x2", layout_scope=layout).layout_id == layout
    converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    assert len(converted.splitlines()) == 3
    assert '"component": "Layout"' not in converted


@pytest.mark.parametrize("layout,variant,action", [
    ("S-title-content-action", "dense", False),
    ("S-title-content-action", "direct", False),
    ("S-title-content-action", "direct-dense", False),
    ("S-title-content-action", "direct-tight", False),
    ("S-title-content-action", "direct-flush", False),
    ("S-title-primary-secondary-action", "dense", False),
    ("S-title-dual-content", "stacked-info", False),
    ("S-title-dual-column-action", "standard", True),
])
def test_small_registered_variants_keep_capacity_contracts(
    layout: str, variant: str, action: bool,
) -> None:
    source = _layout_source(layout, variant, action)
    rows = parse_compact_dsl_rows(source, size="2x2")
    components = [row for row in rows if isinstance(row, ComponentRow)]
    assert match_compact_layout(components, size="2x2", layout_scope=layout).layout_id == layout
    convert_compact_dsl_to_a2ui(source, size="2x2")


@pytest.mark.parametrize("variant", ["hero-support", "label-value", "peer-pair",
                                     "supporting-items"])
def test_small_group_uses_registered_same_region_geometry(variant: str) -> None:
    children = ["main", "support"]
    if variant == "supporting-items":
        children.extend(["third", "fourth"])
    rows = [["root", "Layout", {"layout": "S-title-content"}, ["title", "group"]],
            _leaf("title", "SingleLineTitle"),
            ["group", "Group", {"variant": variant}, children]]
    for identifier in children:
        kind = "EmphasisText" if identifier == "main" else "SecondaryBody"
        rows.append(_leaf(identifier, kind))
    source = _source(rows)
    converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    assert '"component": "Group"' not in converted
    assert '"component": "Layout"' not in converted


@pytest.mark.parametrize("legacy", LEGACY, ids=[item.get("fragment") for item in LEGACY])
def test_legacy_small_samples_round_trip_without_changing_output(legacy: dict) -> None:
    """历史输入保持可解析、可转换，不冻结现行案例的节点 ID、文案和布局。"""
    original = legacy.get("dsl")
    assert isinstance(original, str)
    serialized = serialize_compact_dsl_source(original)
    original_rows = parse_compact_dsl_rows(original, expand_layouts=False)
    assert parse_compact_dsl_rows(serialized, expand_layouts=False) == original_rows
    profile = {"version": "v0.9", "appVersion": "99.0"}
    converted = convert_compact_dsl_to_a2ui(original, size="2x2", protocol_profile=profile)
    assert convert_compact_dsl_to_a2ui(
        serialized, size="2x2", protocol_profile=profile,
    ) == converted
    messages = [json.loads(line) for line in converted.splitlines()]
    assert len(messages) == 3
    for message, operation in zip(
        messages, ("createSurface", "updateComponents", "updateDataModel"), strict=True,
    ):
        assert operation in message


@pytest.mark.parametrize("replacement", [
    ('"variant": "standard"', '"width": 126'),
    ('"variant": "standard"', '"variant": "unknown"'),
    ('"S-title-content-action"', '"W-split-panels"'),
    ('"PillButton"', '"CircleButton"'),
])
def test_small_semantic_source_rejects_wrong_geometry_variant_size_and_role(
    replacement: tuple[str, str],
) -> None:
    source = _layout_source("S-title-content-action").replace(*replacement, 1)
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(source, size="2x2")


def test_documented_small_templates_can_be_completed_and_converted() -> None:
    document = (SOURCE.parents[1] / "layouts/2x2.md").read_text(encoding="utf-8")
    document += (SOURCE.parents[1] / "combinations/2x2.md").read_text(encoding="utf-8")
    layouts = set()
    groups = set()
    for block in re.findall(r"```genui\n([\s\S]*?)\n```", document):
        snippet = [json.loads(line) for line in block.splitlines()]
        root = snippet[0]
        if root[1] == "Group":
            groups.add(root[2].get("variant"))
            continue
        assert root[1] == "Layout"
        layout = root[2].get("layout")
        assert isinstance(layout, str)
        layouts.add(layout)
        variant = root[2].get("variant", "standard")
        action = layout == "S-title-dual-column-action" and len(root[3]) == 4
        rows = [json.loads(line) for line in _layout_source(layout, variant, action).splitlines()]
        rename = dict(zip(rows[0][3], root[3], strict=True))
        by_id = {}
        for row in rows:
            row[0] = rename.get(row[0], row[0])
            if len(row) == 4:
                row[3] = [rename.get(child, child) for child in row[3]]
            by_id[row[0]] = row
        rows[0][2] = root[2]
        for declared in snippet[1:]:
            target = by_id.get(declared[0])
            assert target is not None
            assert target[1] == declared[1]
            target[2] = declared[2]
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")
    assert layouts == set(SMALL_CHILD_ROLES)
    assert groups == {"hero-support", "label-value", "peer-pair", "supporting-items"}
