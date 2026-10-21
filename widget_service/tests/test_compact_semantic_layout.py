"""语义布局和既有编译、布局匹配、绑定及容量接口的契约测试。"""

import json

import pytest

from services.asset_url_mapper import AssetUrlMapper
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _height_budget_components,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    convert_compact_dsl_to_a2ui,
    expand_compact_semantic_layout,
    parse_compact_dsl_rows,
    repair_compact_dsl_binding_paths,
    serialize_compact_dsl_source,
)
from services.compact_layout_runtime import match_compact_layout
from services.compact_plan import (
    compact_plan_optional_drop_candidate,
    evaluate_compact_plan_coverage,
)
from services.compact_repair_strategy import CompactRepairStrategyTracker


def _source(rows: list[list]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _leaf(identifier: str, kind: str = "EmphasisText") -> list:
    props = {"mainText": identifier}
    if kind == "SingleLineTitle":
        props = {"title": "设备概览"}
    elif kind == "InfoBlock":
        props = {"primaryText": identifier, "secondaryText": "读数", "backgroundColor": "#99FFFFFF",
                 "fontColor": "#FF1F4799", "variant": "slot"}
    elif kind in {"PillButton", "CardButton"}:
        props = {"label": "查看设备", "onClick": [{"call": "open", "args": {"id": identifier}}]}
    elif kind == "ProgressCircle":
        props = {"value": 20, "total": 100, "externalText": "20%",
                 "label": identifier, "icon": "test.svg", "fillColor": "#FF000000"}
    return [identifier, kind, props]


def _region(identifier: str, variant: str) -> list[list]:
    children = {"center": ["a"], "title-content": ["title", "a"],
                "title-hero-support": ["title", "a", "b"],
                "title-content-action": ["title", "a", "action"],
                "title-hero-support-action": ["title", "a", "b", "action"],
                "title-two-ratios": ["title", "ring1", "ring2"],
                "four-ratios": ["ring1", "ring2", "ring3", "ring4"]}.get(variant)
    assert children is not None
    ids = []
    rows = []
    for child in children:
        name = identifier + "_" + child
        ids.append(name)
        kind = "EmphasisText"
        if child == "title":
            kind = "SingleLineTitle"
        elif child == "action":
            kind = "PillButton"
        elif child.startswith("ring"):
            kind = "ProgressCircle"
        rows.append(_leaf(name, kind))
    return [[identifier, "Region", {"variant": variant}, ids], *rows]


@pytest.mark.parametrize("variant", ["center", "title-content", "title-hero-support",
                                     "title-content-action"])
def test_compact_region_variants_match_original_split_contract(variant: str) -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]]]
    rows.extend(_region("left", variant))
    rows.extend(_region("right", "center"))
    parsed = parse_compact_dsl_rows(_source(rows), size="2x4")
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    match = match_compact_layout(components, size="2x4", layout_scope="W-plan-guided")
    assert match.layout_id == "W-split-panels"


@pytest.mark.parametrize("layout", ["W-split-panels", "W-content-side-slots"])
def test_title_hero_support_does_not_keep_the_previous_name_as_an_alias(layout: str) -> None:
    region = _region("content", "title-hero-support")
    region[0][2]["variant"] = "title-primary-details"
    if layout == "W-split-panels":
        rows = [["root", "Layout", {"layout": layout}, ["content", "right"]],
                *region, *_region("right", "center")]
    else:
        rows = [["root", "Layout", {"layout": layout}, ["content", "upper", "lower"]],
                *region, _leaf("upper", "InfoBlock"), _leaf("lower", "CardButton")]
    with pytest.raises(CompactDslConversionError, match="当前父区域不支持 Region.variant"):
        parse_compact_dsl_rows(_source(rows), size="2x4")


def test_region_child_count_feedback_reports_ordered_roles() -> None:
    left = _region("left", "title-content-action")
    left[0][3].append("extra")
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *left, _leaf("extra"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError) as caught:
        parse_compact_dsl_rows(_source(rows), size="2x4")
    message = str(caught.value)
    assert "子组件数量应为 [3]，实际为 4" in message
    assert "Region.variant='title-content-action'" in message
    assert "要求的 children 角色为 [title, content, PillButton]" in message
    assert "不要修改展开后的几何" in message


def test_parent_child_count_feedback_reports_content_and_two_fixed_slots() -> None:
    rows = [["root", "Layout", {"layout": "W-content-side-slots"},
             ["content", "upper", "lower", "extra"]],
            *_region("content", "center"), _leaf("upper", "InfoBlock"),
            _leaf("lower", "CardButton"), _leaf("extra", "CardButton")]
    with pytest.raises(CompactDslConversionError) as caught:
        parse_compact_dsl_rows(_source(rows), size="2x4")
    message = str(caught.value)
    assert "子组件数量应为 [3]，实际为 4" in message
    assert "[内容 Region, 上方 InfoBlock/CardButton, 下方 InfoBlock/CardButton]" in message


def test_region_variant_feedback_reports_only_current_parent_options() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "title-hero-support-action"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError) as caught:
        parse_compact_dsl_rows(_source(rows), size="2x4")
    message = str(caught.value)
    assert "实际为 'title-hero-support-action'" in message
    options = message.split("紧凑版 Region 允许的变体：", 1)[1]
    assert "center, title-content, title-content-action, title-hero-support" in options
    assert "title-two-ratios" not in options
    assert "four-ratios" not in options


@pytest.mark.parametrize("variant", ["center", "title-content", "title-hero-support",
                                     "title-content-action", "title-two-ratios",
                                     "title-hero-support-action", "four-ratios"])
@pytest.mark.parametrize("orientation", ["content-left", "content-right"])
def test_wide_region_variants_and_mirror_match_original_contract(variant: str,
                                                               orientation: str) -> None:
    rows = [["root", "Layout", {"layout": "W-content-side-slots", "orientation": orientation},
             ["content", "upper", "lower"]], *_region("content", variant),
            _leaf("upper", "InfoBlock"), _leaf("lower", "CardButton")]
    components = [row for row in parse_compact_dsl_rows(_source(rows), size="2x4")
                  if isinstance(row, ComponentRow)]
    match = match_compact_layout(components, size="2x4", layout_scope="W-plan-guided")
    assert match.layout_id == "W-content-side-slots"


def test_reversed_mixed_fixed_slots_compile_with_warning() -> None:
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["content", "action", "info"]],
        *_region("content", "center"),
        [
            "action",
            "CardButton",
            {
                "label": "查看设备",
                "onClick": [{"call": "open", "args": {"id": "device"}}],
            },
        ],
        [
            "info",
            "InfoBlock",
            {
                "variant": "slot",
                "primaryText": "设备在线",
                "secondaryText": "连接状态",
                "backgroundColor": "#99FFFFFF",
            },
        ],
    ]
    source = _source(rows)
    assert "updateComponents" in convert_compact_dsl_to_a2ui(source, size="2x4")

    result = validate_compact_dsl(
        source,
        task_spec={
            "size": "2x4",
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
            "eventCandidates": [{"call": "open", "args": {"id": "device"}}],
        },
        card_spec={"suggestSize": "2x4"},
    )

    assert result.warnings == (
        "W-content-side-slots 混合固定槽建议将 InfoBlock 放在 CardButton 上方；"
        "当前顺序仍允许转换。",
    )


@pytest.mark.parametrize("variant", ["continuous", "bottom-details", "equal"])
@pytest.mark.parametrize("with_title", [False, True])
def test_top_bottom_variants_and_optional_title(variant: str, with_title: bool) -> None:
    children = ["primary", "details"]
    if with_title:
        children.insert(0, "title")
    rows = [["root", "Layout", {"layout": "W-top-bottom", "variant": variant}, children],
            _leaf("primary"), ["details", "TextBlock", {"items": [
                {"label": "甲", "value": "1项"}, {"label": "乙", "value": "2项"},
            ]}]]
    if with_title:
        rows.append(_leaf("title", "SingleLineTitle"))
    parsed = parse_compact_dsl_rows(_source(rows), size="2x4")
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    match = match_compact_layout(components, size="2x4", layout_scope="W-plan-guided")
    assert match.layout_id == "W-top-bottom"


def test_four_slots_compiles_and_converts_using_existing_recipes() -> None:
    children = ["a", "b", "c", "d"]
    rows = [["root", "Layout", {"layout": "W-four-slots"}, children]]
    rows.extend(_leaf(identifier, "InfoBlock") for identifier in children)
    source = _source(rows)
    components = [row for row in parse_compact_dsl_rows(source) if isinstance(row, ComponentRow)]
    assert match_compact_layout(components, size="2x4", layout_scope="W-four-slots").layout_id
    converted = convert_compact_dsl_to_a2ui(source, size="2x4")
    assert "updateComponents" in converted
    assert '"component": "Layout"' not in converted


def test_business_ids_bindings_events_and_data_rows_are_preserved() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "title-content-action"), *_region("right", "center")]
    rows[3][2] = {"mainText": {"path": "/data/device/reading"}}
    rows.append(["/data/device/reading", "正常"])
    source = _source(rows)
    expanded, origins = expand_compact_semantic_layout(source, size="2x4")
    original = parse_compact_dsl_rows(source, expand_layouts=False)
    parsed = parse_compact_dsl_rows(expanded)
    leaves = {row.component_id: row for row in original
              if isinstance(row, ComponentRow) and row.component_type not in {"Layout", "Region"}}
    for row in parsed:
        if isinstance(row, ComponentRow) and row.component_id in leaves:
            assert row.props == leaves[row.component_id].props
    assert [row for row in original if isinstance(row, DataRow)] == [
        row for row in parsed if isinstance(row, DataRow)]
    assert origins.get("left") == "left"
    assert '"Layout"' in source


@pytest.mark.parametrize("property_name", ["height", "width", "padding", "itemMargin",
                                           "layoutWeight", "justifyContent"])
def test_semantic_layout_rejects_geometry_overrides(property_name: str) -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels", property_name: 1}, ["left", "right"]],
            *_region("left", "center"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError, match="不支持以下语义属性"):
        parse_compact_dsl_rows(_source(rows))


def test_semantic_layout_is_not_accepted_for_two_by_two() -> None:
    source = _source([["root", "Layout", {"layout": "W-four-slots"}, ["a", "b", "c", "d"]],
                      *[_leaf(identifier, "InfoBlock") for identifier in ["a", "b", "c", "d"]]])
    with pytest.raises(CompactDslConversionError, match="仅适用于尺寸 2x4"):
        convert_compact_dsl_to_a2ui(source, size="2x2")


def test_legacy_parse_and_compile_are_unchanged() -> None:
    source = _source([["root", "Column", {"padding": 12}, ["a"]], _leaf("a")])
    expanded, origins = expand_compact_semantic_layout(source, size="2x2")
    assert expanded == source
    assert origins == {}
    assert parse_compact_dsl_rows(source) == parse_compact_dsl_rows(source, expand_layouts=False)


def test_binding_repair_does_not_replace_semantic_source_with_generated_rows() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "center"), *_region("right", "center")]
    rows[2][2] = {"mainText": {"path": "/reading"}}
    rows.append(["/reading", "正常"])
    repaired = repair_compact_dsl_binding_paths(_source(rows),
        task_spec={"dataModelSchema": {"data": {"device": {"reading": {"type": "string"}}}}},
        card_spec={"dataBindings": [{"writeResultTo": "/data/device"}]})
    assert '"Layout"' in repaired
    assert '"Region"' in repaired
    assert "__layout__" not in repaired
    assert "/data/device/reading" in repaired


@pytest.mark.parametrize(
    ("size", "kind", "gap", "origin", "expected_gap"),
    [
        ("2x4", "Column", 8, "region", 0),
        ("2x4", "Column", 6, "region", 6),
        ("2x4", "Row", 8, "region", 8),
        ("2x2", "Column", 8, "region", 8),
        ("2x4", "Column", 8, "container", 8),
        ("2x4", "Column", 8, None, 8),
    ],
)
def test_height_gap_relaxation_only_changes_mapped_generated_wide_columns(
    size: str, kind: str, gap: int, origin: str | None, expected_gap: int,
) -> None:
    row = ComponentRow("container", kind, {"itemMargin": gap, "padding": 12}, ())
    origins = {"container": origin} if origin is not None else {}
    budget = _height_budget_components([row], size, origins)
    assert budget[0].props.get("itemMargin") == expected_gap
    assert budget[0].props.get("padding") == 12
    assert row.props.get("itemMargin") == gap


@pytest.mark.parametrize("item_count", [5, 6])
def test_wide_height_budget_ignores_layout_gaps_but_keeps_content_minimums(item_count: int) -> None:
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["main", "upper", "lower"]],
        ["main", "Region", {"variant": "title-hero-support"}, ["title", "value", "support"]],
        ["title", "SingleLineTitle", {"title": "天气", "icon": "test.svg", "fontSize": 12}],
        ["value", "EmphasizedData", {"value": 29, "unit": "℃", "fontSize": 30}],
        ["support", "SecondaryBody", {"columns": 1, "fontSize": 12,
                                      "items": [{"value": "辅助信息"}] * item_count}],
        _leaf("upper", "InfoBlock"),
        _leaf("lower", "InfoBlock"),
    ]
    source = _source(rows)
    task = {"size": "2x4", "dataModelSchema": {"data": {}},
            "assetCandidates": [{"src": "test.svg", "description": "多色，保留原色"}]}
    if item_count == 5:
        validate_compact_dsl(source, task_spec=task, card_spec={"suggestSize": "2x4"})
    else:
        with pytest.raises(CompactDslValidationError) as caught:
            validate_compact_dsl(source, task_spec=task, card_spec={"suggestSize": "2x4"})
        assert any(item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
                   for item in caught.value.diagnostics)
    expanded = parse_compact_dsl_rows(source, size="2x4")
    sub = next(row for row in expanded
               if isinstance(row, ComponentRow) and row.component_id == "__layout__main__sub")
    assert sub.props.get("itemMargin") == 8


def test_height_budget_is_not_bypassed_and_feedback_locates_original_region() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "title-content-action"), *_region("right", "center")]
    rows[3] = ["left_a", "Group", {"variant": "hero-support"}, ["value", "support"]]
    rows.extend([
        ["value", "EmphasizedData", {"value": {"path": "/data/device/reading"}, "unit": "项"}],
        ["support", "SecondaryBody", {"role": "supporting", "fontSize": 12, "columns": 1,
                                      "items": [{"value": "正常"}, {"value": "已连接"},
                                                {"value": "可用"}]}],
        ["/data/device/reading", 42],
    ])
    task = {"size": "2x4", "dataModelSchema": {"data": {"device": {
        "reading": {"type": "integer", "sampleValue": 42},
    }}}, "assetCandidates": [],
            "eventCandidates": [{"call": "open", "args": {"id": "left_action"}}]}
    with pytest.raises(CompactDslValidationError) as caught:
        validate_compact_dsl(_source(rows), task_spec=task, card_spec={},
                             layout_scope="W-plan-guided")
    diagnostics = caught.value.diagnostics
    layout_diagnostics = [item for item in diagnostics
                          if item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"]
    assert layout_diagnostics, caught.value.errors
    assert any(item.component_id == "left" and item.evidence_source == "expanded"
               for item in layout_diagnostics)
    assert any(item.source_line == 2 and item.property_path is None for item in layout_diagnostics)


def test_asset_restoration_preserves_semantic_source() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "center"), *_region("right", "center")]
    rows[2][2]["icon"] = "https://example.test/device.svg"
    mapper = AssetUrlMapper({"device.svg": "https://example.test/device.svg"}, {"device.svg"})
    restored = mapper.restore_design_token(_source(rows))
    assert '"Layout"' in restored and '"Region"' in restored
    assert "__layout__" not in restored
    assert "https://example.test" not in restored


def test_plan_coverage_and_drop_use_original_business_ids() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "center"), *_region("right", "center")]
    rows[2][2] = {"mainText": {"path": "/data/device/a"}}
    rows[4][2] = {"mainText": {"path": "/data/device/b"}}
    rows.extend([["/data/device/a", "正常"], ["/data/device/b", "已连接"]])
    source = _source(rows)
    facts = [{"dataId": "/data/device/a", "requirement": "设备状态", "priority": "must"},
             {"dataId": "/data/device/b", "requirement": "连接状态", "priority": "should"}]
    plan = {"info_required": facts}
    task = {"dataModelSchema": {"data": {"device": {
        "a": {"type": "string"}, "b": {"type": "string"},
    }}}}
    assert evaluate_compact_plan_coverage(source, plan, task).errors == ()
    candidate = compact_plan_optional_drop_candidate(source, plan, task)
    assert candidate is not None
    assert candidate.component_id == "right_a"
    assert candidate.fact_indexes == (1,)


def test_cycle_is_rejected_before_semantic_recursion() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            ["left", "Region", {"variant": "center"}, ["group"]],
            ["group", "Group", {"variant": "hero-support"}, ["group", "a"]],
            _leaf("a"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError):
        parse_compact_dsl_rows(_source(rows))


def test_region_does_not_hide_an_extra_button_inside_group() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            ["left", "Region", {"variant": "center"}, ["group"]],
            ["group", "Group", {"variant": "hero-support"}, ["a", "extra"]],
            _leaf("a"), _leaf("extra", "PillButton"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError, match="底部动作角色"):
        parse_compact_dsl_rows(_source(rows))


def test_saved_source_repairs_json_without_expanding_semantic_layout() -> None:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            *_region("left", "title-content-action"), *_region("right", "center")]
    source = _source(rows)
    valid_source = serialize_compact_dsl_source(source)
    broken_source = source.replace('"PillButton", {', '"PillButton", ')
    repaired = serialize_compact_dsl_source(broken_source)
    assert repaired == valid_source
    assert '"Layout"' in repaired and '"Region"' in repaired
    assert "__layout__" not in repaired
    for line in repaired.splitlines():
        assert isinstance(json.loads(line), list)


@pytest.mark.asyncio
async def test_online_artifact_saves_valid_semantic_source_after_json_repair(
    monkeypatch, isolated_theme_stage,
) -> None:
    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from core.errors import GenerationStatus
    from custom.a2ui_model_client import A2UIModelClient
    from models.service import ArtifactSaveResult
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    rows = [["root", "Layout", {"layout": "W-four-slots", "linearGradient": {
        "direction": "RightBottom", "colors": [["#FFCBDDFE", 0], ["#FFF1F6FE", 1]],
    }}, ["a", "b", "c", "d"]],
        *[_leaf(identifier, "InfoBlock") for identifier in ("a", "b", "c", "d")]]
    valid = _source(rows)
    broken = valid.replace('"InfoBlock", {', '"InfoBlock", ', 1)
    saved = []
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template",
                        staticmethod(lambda: False))
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation",
                        staticmethod(lambda: False))
    monkeypatch.setattr(A2UIModelClient, "generate", lambda *_args, **_kwargs: broken)

    def save(store, _artifact):
        saved.append(store.design_token)
        return ArtifactSaveResult(artifactUrl="https://artifact.test/result",
                                  artifactDigest="sha256:x")

    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(uid="semantic-test", prdVer="12.0.0.1",
        device={"romVersion": "6.0"}, userQuery="静态设备读数", size="2x4",
        title="设备读数", description="验证语义源保存")
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.SUCCESS
    from services.layout_theme_contract import strip_source_colors

    assert saved == [serialize_compact_dsl_source(strip_source_colors(valid))]
    assert "__layout__" not in saved[0]


@pytest.mark.parametrize("own_title", [True, False])
def test_metric_label_crosses_only_compiler_wrappers_not_neighbor_region(own_title) -> None:
    own_children = ["left_title", "score"] if own_title else ["score"]
    own_variant = "title-content" if own_title else "center"
    rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": own_variant}, own_children],
        ["score", "EmphasizedData", {"value": {"path": "/data/health/sleepScore"}, "unit": "分"}],
        ["right", "Region", {"variant": "title-content"}, ["right_title", "state"]],
        ["right_title", "SingleLineTitle", {"title": "设备得分"}],
        ["state", "SecondaryBody", {"role": "supporting", "items": [{"value": "已连接"}]}],
        ["/data/health/sleepScore", 82],
    ]
    if own_title:
        rows.append(["left_title", "SingleLineTitle", {"title": "睡眠得分"}])
    task = {"size": "2x4", "dataModelSchema": {"data": {"health": {"sleepScore": {
        "type": "integer", "description": "睡眠综合得分，取值范围0-100。", "sampleValue": 82,
    }}}}}
    if own_title:
        validate_compact_dsl(_source(rows), task_spec=task, card_spec={},
                             layout_scope="W-plan-guided")
    else:
        with pytest.raises(CompactDslValidationError) as caught:
            validate_compact_dsl(_source(rows), task_spec=task, card_spec={},
                                 layout_scope="W-plan-guided")
        assert any(item.code == "COMPACT_DISPLAY_AMBIGUOUS_METRIC"
                   for item in caught.value.diagnostics)


@pytest.mark.parametrize("title_kind", ["title-count", "DoubleLineTitle"])
def test_existing_title_variations_keep_same_registered_parent(title_kind) -> None:
    rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "title-content"}, ["header", "value"]],
        _leaf("value"), *_region("right", "center"),
    ]
    if title_kind == "title-count":
        rows.extend([
            ["header", "Group", {"variant": "title-count"}, ["title", "count"]],
            ["title", "SingleLineTitle", {"title": "日程"}],
            ["count", "Badge", {"value": 3, "fontColor": "#FF1F4799",
                                "backgroundColor": "#331F4799"}],
        ])
    else:
        rows.append(["header", "DoubleLineTitle", {"title": "设备", "secondaryInfo": "客厅"}])
    parsed = parse_compact_dsl_rows(_source(rows), size="2x4")
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    assert match_compact_layout(components, size="2x4", layout_scope="W-plan-guided").layout_id
    assert "updateComponents" in convert_compact_dsl_to_a2ui(_source(rows), size="2x4")


def test_four_plain_content_items_preserve_previous_wide_grid_capability() -> None:
    children = ["a", "b", "c", "d"]
    rows = [["root", "Layout", {"layout": "W-content-side-slots"}, ["content", "up", "down"]],
            ["content", "Region", {"variant": "four-items"}, children],
            _leaf("up", "InfoBlock"), _leaf("down", "InfoBlock")]
    rows.extend(_leaf(identifier) for identifier in children)
    parsed = parse_compact_dsl_rows(_source(rows))
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    assert match_compact_layout(components, size="2x4", layout_scope="W-plan-guided").layout_id
    assert "updateComponents" in convert_compact_dsl_to_a2ui(_source(rows), size="2x4")


@pytest.mark.parametrize("geometry_override", [True, False])
def test_semantic_errors_use_existing_local_or_layout_repair_route(geometry_override) -> None:
    props = {"layout": "unknown"}
    if geometry_override:
        props = {"layout": "W-split-panels", "height": 126}
    rows = [["root", "Layout", props, ["left", "right"]],
            *_region("left", "center"), *_region("right", "center")]
    with pytest.raises(CompactDslConversionError) as caught:
        parse_compact_dsl_rows(_source(rows))
    issue = {"code": "COMPACT_DSL_VALIDATION_FAILED", "stage": "validation",
             "message": str(caught.value)}
    directive = CompactRepairStrategyTracker().next_directive(_source(rows), [issue])
    if geometry_override:
        assert directive.scope == "component"
    else:
        assert directive.scope == "parent_layout"
