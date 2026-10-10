"""二维重叠、合法叠放与校验修复闭环。"""

import json
from typing import Any

import pytest

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.card_validation.compact_geometry import GeometryResult, validate_compact_geometry
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    expand_high_level_component_rows,
    parse_compact_dsl_rows,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.prompt_builder import PromptBuilder
from services.retry_controller import RetryController


def _source(rows: list[list[Any]]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _check(rows: list[list[Any]], size: str = "2x4") -> GeometryResult:
    parsed = parse_compact_dsl_rows(_source(rows))
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    expanded = expand_high_level_component_rows(components, size=size)
    return validate_compact_geometry(expanded, size=size)


def _text(name: str, **props: Any) -> list[Any]:
    return [name, "Text", {"width": 40, "height": 20, "content": name, **props}]


def _pair(layout: str = "Stack", **props: Any) -> list[list[Any]]:
    return [["root", layout, props, ["first", "second"]], _text("first"), _text("second")]


def test_explicit_stack_overlap_reports_pair_and_both_axes() -> None:
    result = _check(_pair())
    assert len(result.errors) == 1
    assert "COMPACT_LAYOUT_OVERLAP: components first and second" in result.errors[0]
    assert "40.00vp horizontally and 20.00vp vertically" in result.errors[0]


@pytest.mark.parametrize("layout", ["Row", "Column", "List"])
def test_flow_layouts_do_not_overlap(layout: str) -> None:
    result = _check(_pair(layout, padding=12, itemMargin=4))
    assert result.errors == []
    assert result.warnings == []


@pytest.mark.parametrize("overlap", [0, 1.5, 1.6, 8])
def test_negative_margin_overlap_tolerance(overlap: float) -> None:
    rows = _pair("Row")
    rows[2] = _text("second", margin={"left": -overlap})
    result = _check(rows)
    assert bool(result.errors) is (overlap > 1.5)


def test_cross_branch_overflow_is_compared() -> None:
    rows = [
        ["root", "Column", {}, ["upper", "lower"]],
        ["upper", "Row", {"width": 100, "height": 20, "flexShrink": 0}, ["tall"]],
        ["lower", "Row", {"width": 100, "height": 20, "flexShrink": 0}, ["short"]],
        _text("tall", height=40),
        _text("short"),
    ]
    result = _check(rows)
    assert any("tall and short" in error for error in result.errors)


@pytest.mark.parametrize("background_width", [300, 40])
def test_only_full_noninteractive_first_image_is_background(background_width: int) -> None:
    rows = [
        ["root", "Stack", {}, ["image", "label"]],
        ["image", "Image", {"src": "resources/bg.png", "width": background_width, "height": 150}],
        _text("label"),
    ]
    result = _check(rows)
    assert bool(result.errors) is (background_width != 300)


def test_interactive_full_image_is_not_background() -> None:
    rows = [
        ["root", "Stack", {}, ["image", "label"]],
        ["image", "Image", {"width": 300, "height": 150, "onClick": [{"call": "test"}]}],
        _text("label"),
    ]
    assert _check(rows).errors


def test_interactive_parent_and_child_are_not_collision() -> None:
    rows = [
        ["root", "Column", {"onClick": [{"call": "test"}]}, ["label"]],
        _text("label"),
    ]
    assert _check(rows).errors == []


def _circle(name: str) -> list[Any]:
    return [
        name,
        "ProgressCircleSingle",
        {
            "value": 68,
            "total": 100,
            "displayValue": "68%",
            "label": "电量",
            "icon": "resources/base/media/battery_leaf_fill.svg",
            "fontColor": "#FF1F4799",
            "color": "#FF1F4799",
            "backgroundColor": "#331F4799",
        },
    ]


def test_trusted_progress_recipe_allows_ring_and_center_icon() -> None:
    result = _check([["root", "Column", {}, ["circle"]], _circle("circle")])
    assert result.errors == []
    assert not any("OVERLAP" in warning for warning in result.warnings)
    assert len(result.boxes) > 1


def test_distinct_recipes_are_still_compared() -> None:
    result = _check(
        [
            ["root", "Stack", {}, ["first", "second"]],
            _circle("first"),
            _circle("second"),
        ]
    )
    diagnostics = result.errors + result.warnings
    assert any("first_ring and second_ring" in message for message in diagnostics)


@pytest.mark.parametrize(
    "props", [{"visibility": "none"}, {"visibility": "hidden"}, {"opacity": 0}]
)
def test_invisible_components_do_not_collide(props: dict[str, Any]) -> None:
    rows = _pair()
    rows[2] = _text("second", **props)
    assert _check(rows).errors == []


def test_hidden_parent_hides_descendants() -> None:
    rows = _pair(visibility="hidden")
    assert _check(rows).boxes == []


def test_estimated_text_overlap_is_error() -> None:
    rows = _pair()
    rows[2] = ["second", "Text", {"content": "动态或换行文本"}]
    result = _check(rows)
    assert any("COMPACT_LAYOUT_ESTIMATED_OVERLAP" in error for error in result.errors)


def test_unknown_geometry_is_explicit_warning() -> None:
    rows = [["root", "Column", {}, ["image"]], ["image", "Image", {}]]
    result = _check(rows)
    assert result.errors == []
    assert any("COMPACT_LAYOUT_UNVERIFIED" in warning for warning in result.warnings)


def test_clipping_reports_lost_content_and_excludes_invisible_overlap() -> None:
    rows = [
        ["root", "Column", {}, ["clipper", "second"]],
        ["clipper", "Row", {"width": 100, "height": 20, "clip": True}, ["first"]],
        _text("first", height=40),
        _text("second"),
    ]
    result = _check(rows)
    assert any("COMPACT_LAYOUT_CLIPPED" in warning for warning in result.warnings)
    assert not any("COMPACT_LAYOUT_OVERLAP" in error for error in result.errors)


def test_weight_minimum_and_maximum_redistribute_width() -> None:
    rows = [
        ["root", "Row", {"padding": 10, "itemMargin": 10}, ["first", "second"]],
        _text("first", layoutWeight=1, constraintSize={"maxWidth": 50}),
        _text("second", layoutWeight=1, constraintSize={"minWidth": 60}),
    ]
    result = _check(rows)
    assert result.errors == []
    assert result.boxes[0].box.width == 50
    assert result.boxes[1].box.width == 220
    assert result.boxes[1].box.x == 70


def test_shrink_respects_minimum_and_does_not_create_false_overlap() -> None:
    rows = [
        ["root", "Row", {}, ["first", "second"]],
        _text("first", width=250, constraintSize={"minWidth": 200}),
        _text("second", width=250),
    ]
    result = _check(rows)
    assert result.errors == []
    assert [paint.box.width for paint in result.boxes] == [200, 100]


def test_percent_match_parent_padding_and_margins() -> None:
    rows = [
        ["root", "Row", {"padding": 10, "alignItems": "end"}, ["label"]],
        _text("label", width="50%", height="matchParent", margin={"left": 5}),
    ]
    result = _check(rows)
    box = result.boxes[0].box
    assert (box.x, box.y, box.width, box.height) == (15, 10, 140, 130)


def test_stack_bottom_end_alignment() -> None:
    result = _check([["root", "Stack", {"alignContent": "bottomEnd"}, ["label"]], _text("label")])
    box = result.boxes[0].box
    assert (box.x, box.y) == (260, 130)


@pytest.mark.parametrize("justify, expected", [("end", 220), ("center", 110), ("spaceBetween", 0)])
def test_flow_justification(justify: str, expected: float) -> None:
    result = _check(_pair("Row", justifyContent=justify))
    assert result.boxes[0].box.x == expected
    assert result.errors == []


def test_unmodeled_border_keeps_estimate_marker_and_reports_overlap() -> None:
    result = _check(_pair(borderWidth=2))
    assert any("COMPACT_LAYOUT_UNVERIFIED" in warning for warning in result.warnings)
    assert any("COMPACT_LAYOUT_ESTIMATED_OVERLAP" in error for error in result.errors)


def test_malformed_alignment_does_not_crash_geometry() -> None:
    rows = parse_compact_dsl_rows(_source(_pair("Row")))
    components = [row for row in rows if isinstance(row, ComponentRow)]
    components[0].props.update({"justifyContent": {}, "alignItems": [], "visibility": {}})
    result = validate_compact_geometry(components, size="2x4")
    assert any("COMPACT_LAYOUT_UNVERIFIED" in warning for warning in result.warnings)


def test_cycle_and_missing_child_are_reported_without_recursion_error() -> None:
    result = _check([["root", "Column", {}, ["root", "missing"]]])
    assert result.errors == []
    assert any("cycle" in warning for warning in result.warnings)
    assert any("missing" in warning for warning in result.warnings)


def test_deep_tree_is_bounded() -> None:
    rows: list[list[Any]] = [["root", "Column", {}, ["n0"]]]
    for index in range(80):
        rows.append([f"n{index}", "Column", {}, [f"n{index + 1}"]])
    rows.append(_text("n80"))
    assert any("depth limit" in warning for warning in _check(rows).warnings)


def test_diagnostics_are_bounded() -> None:
    names = [f"n{index}" for index in range(20)]
    rows: list[list[Any]] = [["root", "Stack", {}, names]]
    rows.extend(_text(name) for name in names)
    result = _check(rows)
    assert len(result.errors) == 32
    assert any("limit reached" in warning for warning in result.warnings)


def test_duplicate_ids_and_unknown_size_are_not_silently_accepted() -> None:
    parsed = parse_compact_dsl_rows(_source(_pair()))
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    duplicated = validate_compact_geometry([*components, components[0]], size="2x4")
    assert duplicated.warnings
    unknown = validate_compact_geometry(components, size="unknown")
    assert unknown.warnings


def test_public_validator_rejects_definite_overlap() -> None:
    with pytest.raises(CompactDslValidationError, match="COMPACT_LAYOUT_OVERLAP"):
        validate_compact_dsl(_source(_pair()), task_spec={"size": "2x4"}, card_spec={})


def test_public_validator_rejects_estimated_overlap() -> None:
    rows = _pair()
    rows[2] = ["second", "Text", {"content": "估算"}]
    with pytest.raises(CompactDslValidationError, match="COMPACT_LAYOUT_ESTIMATED_OVERLAP"):
        validate_compact_dsl(
            _source(rows), task_spec={"size": "2x4", "dataModelSchema": {}}, card_spec={}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("fixed", [True, False])
@pytest.mark.parametrize("estimated", [False, True])
async def test_overlap_enters_targeted_repair_and_is_rechecked(
    fixed: bool, estimated: bool
) -> None:
    context = DslProcessingContext(
        size="2x4",
        task_spec={"size": "2x4", "appVersion": "12.0.0.1", "dataModelSchema": {}},
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        protocol_profile={"sizes": {"2x4": {"width": 300, "height": 150}}},
    )
    processor = DesignCompactProcessor()
    rows = _pair()
    expected_code = "COMPACT_LAYOUT_OVERLAP"
    if estimated:
        rows[2] = ["second", "Text", {"content": "second"}]
        expected_code = "COMPACT_LAYOUT_ESTIMATED_OVERLAP"
    invalid = _source(rows)
    prompts: list[list[dict[str, str]]] = []

    def evaluate(source: str) -> list[str]:
        result = processor.process(source, context)
        return [issue.repair_message() for issue in result.errors]

    def repair(source: str, errors: list[str]) -> str:
        assert any(expected_code in error for error in errors)
        prompts.append(
            PromptBuilder().build_repair(
                [
                    {"role": "system", "content": "生成 Compact DSL"},
                    {"role": "user", "content": "保留两个内容，修复重叠"},
                ],
                source,
                [
                    {
                        "stage": "validation",
                        "code": "COMPACT_DSL_VALIDATION_FAILED",
                        "message": error,
                    }
                    for error in errors
                ],
                dsl_format="design-compact-dsl",
            )
        )
        return _source(_pair("Row")) if fixed else invalid

    result = await RetryController().run(
        lambda: invalid,
        evaluate,
        retry_on_quality_failure=True,
        max_repair_attempts=1,
        repair=repair,
    )
    assert result.repairAttempted
    assert result.retryCount == 1
    assert bool(result.errors) is not fixed
    assert len(prompts) == 1
    payload_text = prompts[0][1].get("content")
    assert isinstance(payload_text, str)
    payload = json.loads(payload_text)
    assert payload.get("invalidSourceDsl") == invalid
    assert expected_code in str(payload.get("qualityErrors"))
