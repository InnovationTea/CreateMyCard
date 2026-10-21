"""提示词职责、生成可用Props及示例的结构守卫，不要求旧句子逐字保留。"""

import re
from pathlib import Path

import pytest

from services.compact_prompt_loader import FRAGMENT, read_prompt

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_merged_contract_separates_theme_and_visible_fact_ownership(size: str) -> None:
    from services.layout_theme_contract import layout_only_prompt

    source = read_prompt(SOURCE, "create", size=size)
    messages = layout_only_prompt([{"role": "system", "content": source}])
    content = messages[0].get("content", "")
    assert "恰好一个可见信息位置" in content
    assert "图形驱动 value 不另计" in content
    assert "surfaceRole" in content
    assert "不选择主题" in content
    assert not re.search(r"#[0-9a-fA-F]{8}\b", content)


def test_merged_plan_and_repair_preserve_pr568_fact_contract() -> None:
    plan = read_prompt(SOURCE, "plan")
    repair = read_prompt(SOURCE, "repair")
    assert "仅一个可见 placement" in plan
    assert "不把同一事实同时分配给 value 和 displayValue" in plan
    assert "duplicateFacts/occurrences" in repair
    assert "仅移除重复引用，保留其它事实" in repair
    assert "不得改 Plan、删唯一展示或数据行" in repair


# main fd8ce68 生成可用字段；排除明确只兼容旧输入的标题fillColor和圆环宽高。
EXPECTED_PROPS = {
    "SingleLineTitle": [
        "fontSize",
        "icon",
        "title"
    ],
    "DoubleLineTitle": [
        "fontSize",
        "secondaryInfo",
        "title"
    ],
    "Badge": [
        "backgroundColor",
        "value"
    ],
    "EmphasizedData": [
        "fontSize",
        "unit",
        "value"
    ],
    "EmphasisText": [
        "fontSize",
        "mainText",
        "secondaryText"
    ],
    "SecondaryBody": [
        "columns",
        "fontSize",
        "items",
        "items[].label",
        "items[].maxLines",
        "items[].value",
        "separator"
    ],
    "DataDisplay": [
        "icon",
        "label",
        "supportingText",
        "value"
    ],
    "InfoBlock": [
        "backgroundColor",
        "fillColor",
        "primaryText",
        "secondaryText",
        "unit",
        "variant",
        "visual"
    ],
    "TableText": [
        "fontSize",
        "items",
        "items[].label",
        "items[].value"
    ],
    "SummaryList": [
        "items"
    ],
    "ProgressCircle": [
        "accessibility",
        "backgroundColor",
        "color",
        "externalText",
        "fillColor",
        "icon"
    ],
    "ProgressLine2": [
        "backgroundColor",
        "color",
        "displayValue",
        "total",
        "unit",
        "value"
    ],
    "ProgressCircleSingle": [
        "backgroundColor",
        "color",
        "displayValue",
        "icon",
        "label",
        "secondaryLabel",
        "total",
        "value"
    ],
    "H_BarChart": [
        "barColor",
        "items",
        "items[].label",
        "items[].percent",
        "items[].valueUnit",
        "trackColor"
    ],
    "NumericRatioStack": [
        "direction",
        "fillColor",
        "items",
        "items[].icon",
        "items[].unit",
        "items[].value"
    ],
    "EventCard": [
        "density",
        "items",
        "items[].location",
        "items[].time",
        "items[].title"
    ],
    "PillButton": [
        "icon",
        "label",
        "onClick"
    ],
    "CircleButton": [
        "accessibility",
        "icon",
        "onClick"
    ],
    "TopTextBottomValue": [
        "dividerColor",
        "items",
        "items[].label",
        "items[].unit",
        "items[].value"
    ],
    "TextBlock": [
        "items",
        "items[].label",
        "items[].value"
    ],
    "CardButton": [
        "fillColor",
        "icon",
        "label",
        "labelLines",
        "onClick"
    ]
}


def _component_props(name: str) -> set[str]:
    result = set()
    pattern = re.compile(
        rf"^### [^\n]*`{name}`[^\n]*\n([\s\S]*?)(?=^### |^## |^<!-- /prompt|\Z)",
        re.M,
    )
    for source in (SOURCE / "components").glob("*.md"):
        match = pattern.search(source.read_text(encoding="utf-8"))
        if match is None:
            continue
        for line in match.group(1).splitlines():
            if line.startswith("| `"):
                cell = line.split("|")[1]
                result.update(re.findall(r"`([^`]+)`", cell))
    return result


@pytest.mark.parametrize("name", EXPECTED_PROPS)
def test_generated_props_preserved_at_exactly_one_owner(name: str) -> None:
    expected = EXPECTED_PROPS.get(name)
    assert expected is not None
    assert _component_props(name) == set(expected)
    owners = 0
    for source in (SOURCE / "components").glob("*.md"):
        pattern = rf"^### [^\n]*`{name}`[^\n]*\n"
        owners += len(re.findall(pattern, source.read_text(encoding="utf-8"), re.M))
    assert owners == 1


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_frontmatter_and_maintenance_notes_never_reach_model(size: str) -> None:
    prompt = read_prompt(SOURCE, "create", size=size)
    for excluded in ("description:", "name: card-", "维护校对", "runtime/layout-contracts"):
        assert excluded not in prompt
    assert "Sub-118" not in prompt
    assert "Sub-140" not in prompt
    assert "合法可点击 Row/Column" not in prompt


def test_parent_routes_and_group_variants_have_different_owners() -> None:
    common = dict(FRAGMENT.findall(
        (SOURCE / "layouts/common.md").read_text(encoding="utf-8")
    ))
    routing = common.get("routing", "")
    assert "S-title-content" not in routing
    assert "W-split-panels" not in routing
    for size in ("2x2", "2x4"):
        composition = (SOURCE / "combinations" / f"{size}.md").read_text(encoding="utf-8")
        layouts = (SOURCE / "layouts" / f"{size}.md").read_text(encoding="utf-8")
        assert "| hero-support |" in composition
        assert "| hero-support |" not in layouts
        assert "| label-value |" in composition
        assert "| label-value |" not in layouts


def test_plan_and_repair_retain_information_authorization_boundary() -> None:
    plan = read_prompt(SOURCE, "plan", size="2x4")
    repair = read_prompt(SOURCE, "repair", size="2x4")
    for field in ("info_required", "priority", "dataId", "actionId", "text",
                  "componentHints", "layoutHints", "assetAssignments", "composition"):
        assert field in plan
    assert "仅填写 Schema 声明的字段" in plan
    assert "其它数组成员" in plan
    for field in ("componentId", "allowedOmittedFactIndexes", "approvedOmissions"):
        assert field in repair
    assert "Action 始终不可删" in repair
    assert "不沿用失败旧拓扑" in repair
    assert "一个非Action组件" in repair
