"""Issue #538：三个固定圆环超过分区宽度，须拦截并进入既有修复复检。"""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.diagnostics import DiagnosticCollector
from services.card_validation.compact_validation.semantic.layout.horizontal import (
    _collect_horizontal_budget_errors,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    DataRow,
    build_compact_data_model,
    expand_high_level_component_rows,
    normalize_mixed_font_text_rows,
    parse_compact_dsl_rows,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.retry_controller import RetryController

_PROFILE = {"sizes": {"2x4": {"width": 300, "height": 150}}}
_ASSET = "resources/battery.svg"
_TASK = {
    "size": "2x4",
    "appVersion": "12.0.0.1",
    "dataModelSchema": {"data": {}},
    "assetCandidates": [{"src": _ASSET}],
}


def _source(*, count: int = 3, weight: int = 1, clip: bool = True) -> str:
    ids = [f"ring_{index}" for index in range(count)]
    rows = [
        [
            "root",
            "Row",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
                "itemMargin": 12,
                "clip": clip,
            },
            ["left", "right"],
        ],
        [
            "left",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 8,
                "layoutWeight": 1,
            },
            ["label"],
        ],
        ["label", "SingleLineTitle", {"title": "电量"}],
        [
            "right",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 8,
                "layoutWeight": weight,
                "itemMargin": 6,
                "clip": clip,
            },
            ["title", "buds"],
        ],
        ["title", "SingleLineTitle", {"title": "耳机已连接"}],
        ["buds", "Row", {"width": "matchParent", "itemMargin": 6, "layoutWeight": 1}, ids],
    ]
    for identifier in ids:
        rows.append(
            [
                identifier,
                "ProgressCircle",
                {
                    "externalText": "80%",
                    "icon": _ASSET,
                    "accessibility": {"label": "耳机电量"},
                    "width": 52,
                    "height": 68,
                    "fillColor": "#991F4799",
                    "color": "#FF1F4799",
                    "backgroundColor": "#331F4799",
                },
            ]
        )
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _expanded(source: str) -> list[ComponentRow]:
    rows = parse_compact_dsl_rows(source)
    data = build_compact_data_model([row for row in rows if isinstance(row, DataRow)])
    components = [row for row in rows if isinstance(row, ComponentRow)]
    expanded = expand_high_level_component_rows(components, size="2x4", data_model=data)
    return normalize_mixed_font_text_rows(expanded, data_model=data)


def _check(components: list[ComponentRow]) -> DiagnosticCollector:
    errors = DiagnosticCollector()
    _collect_horizontal_budget_errors(components, _TASK, {}, errors, _PROFILE)
    return errors


def test_original_issue_fixture_reports_exact_horizontal_budget() -> None:
    path = Path(__file__).parent / "fixtures/compact_horizontal_overflow/input.jsonl"
    errors = _check(_expanded(path.read_text(encoding="utf-8")))
    assert len(errors.records) == 1
    diagnostic = errors.records[0]
    assert not isinstance(diagnostic, str)
    assert diagnostic.component_id == "buds_row"
    assert diagnostic.actual.get("minimumRequiredWidth") == 168
    assert diagnostic.actual.get("overflow") == 52
    assert diagnostic.expected.get("maximumWidth") == 116
    assert diagnostic.evidence_source == "expanded"
    occupancy = diagnostic.actual.get("occupancy")
    assert isinstance(occupancy, list)
    assert [item.get("componentId") for item in occupancy[:-1]] == [
        "case_ring",
        "left_ring",
        "right_ring",
    ]


@pytest.mark.parametrize("clip", [True, False])
def test_public_validation_reports_width_and_repair_hint(clip: bool) -> None:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(_source(clip=clip), task_spec=_TASK, card_spec={})
    diagnostics = captured.value.diagnostics
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == "COMPACT_LAYOUT_WIDTH_OVERFLOW"
    assert diagnostic.component_id == "buds"
    assert diagnostic.actual.get("overflow") == 52
    assert diagnostic.fix_hint is not None
    assert "绑定" in diagnostic.fix_hint
    assert "SingleLineTitle" not in str(captured.value)


@pytest.mark.parametrize("count, weight", [(2, 1), (3, 3)])
def test_legal_layout_preserves_existing_nonblocking_warning(count: int, weight: int) -> None:
    result = validate_compact_dsl(
        _source(count=count, weight=weight),
        task_spec=_TASK,
        card_spec={"dataBindings": [{"writeResultTo": "/data/unused"}]},
    )
    assert result.warnings == (
        "/data/unused: declared data capability is not used by any component.",
    )


def _basic_rows(*, width: int = 100, gap: int = 6) -> list[ComponentRow]:
    return [
        ComponentRow("root", "Column", {"width": "matchParent"}, ("row",)),
        ComponentRow("row", "Row", {"width": width, "itemMargin": gap}, ("a", "b")),
        ComponentRow("a", "Image", {"width": 52, "height": 52, "flexShrink": 0}, ()),
        ComponentRow("b", "Image", {"width": 52, "height": 52, "flexShrink": 0}, ()),
    ]


def test_nested_weighted_wrappers_cannot_hide_fixed_descendants() -> None:
    rows = _basic_rows()
    rows[1] = replace(rows[1], children=("wrap_a", "wrap_b"))
    rows.extend(
        [
            ComponentRow("wrap_a", "Column", {"layoutWeight": 1}, ("a",)),
            ComponentRow("wrap_b", "Stack", {"layoutWeight": 1}, ("b",)),
        ]
    )
    errors = _check(rows)
    assert len(errors) == 1
    assert "110vp within 100vp" in errors[0]


def test_padding_margins_and_spacing_are_counted() -> None:
    rows = _basic_rows(width=130)
    rows[1] = replace(rows[1], props={"width": 130, "padding": 8, "space": 6})
    rows[2] = replace(rows[2], props={**rows[2].props, "margin": {"left": 4, "right": 4}})
    assert "118vp within 114vp" in _check(rows)[0]


@pytest.mark.parametrize("visibility", ["none", "hidden"])
def test_none_removes_layout_space_but_hidden_keeps_it(visibility: str) -> None:
    rows = _basic_rows()
    rows[3] = replace(rows[3], props={**rows[3].props, "visibility": visibility})
    assert bool(_check(rows)) is (visibility == "hidden")


def test_shrinkable_leaf_and_unknown_text_are_not_fixed_minimum_widths() -> None:
    rows = _basic_rows()
    rows[2] = replace(rows[2], props={"width": 52, "height": 52, "flexShrink": 1})
    rows[3] = replace(rows[3], component_type="Text", props={"content": {"path": "/data/x"}})
    assert not _check(rows)


@pytest.mark.parametrize("change", ["dynamic", "constraints", "cycle", "missing", "duplicate"])
def test_unknown_geometry_and_invalid_tree_do_not_create_width_facts(change: str) -> None:
    rows = _basic_rows()
    if change == "dynamic":
        rows[1] = replace(rows[1], props={"width": "{{ ${/data/width} }}"})
    elif change == "constraints":
        rows[1] = replace(rows[1], props={**rows[1].props, "minWidth": 120})
    elif change == "cycle":
        rows[1] = replace(rows[1], children=("root",))
    elif change == "missing":
        rows[1] = replace(rows[1], children=("absent",))
    else:
        rows.append(rows[2])
    assert not _check(rows)


@pytest.mark.parametrize("fixed", [False, True])
@pytest.mark.asyncio
async def test_pipeline_repairs_and_rechecks_width_without_dropping_rings(fixed: bool) -> None:
    context = DslProcessingContext(
        size="2x4",
        task_spec=deepcopy(_TASK),
        card_spec={},
        protocol_profile=_PROFILE,
    )
    processor = DesignCompactProcessor()
    attempts: list[list[str]] = []

    def evaluate(source: str) -> list[str]:
        return [issue.repair_message() for issue in processor.process(source, context).errors]

    def repair(_source_dsl: str, errors: list[str]) -> str:
        attempts.append(errors)
        assert any("horizontal layout requires" in message for message in errors)
        return _source(weight=3 if fixed else 1)

    result = await RetryController().run(
        lambda: _source(),
        evaluate,
        retry_on_quality_failure=True,
        max_repair_attempts=2,
        repair=repair,
    )
    assert result.retryCount == (1 if fixed else 2)
    assert bool(result.errors) is not fixed
    assert len(attempts) == result.retryCount
    assert result.result.count('"ProgressCircle"') == 3


def test_template_skip_remains_at_pipeline_boundary() -> None:
    context = DslProcessingContext(
        size="2x4",
        task_spec=deepcopy(_TASK),
        card_spec={},
        protocol_profile=_PROFILE,
        skip_compact_dsl_validation=True,
    )
    result = DesignCompactProcessor().process(_source(), context)
    assert not any("horizontal layout requires" in issue.message for issue in result.errors)


def test_pipeline_preserves_structured_width_evidence() -> None:
    context = DslProcessingContext(
        size="2x4",
        task_spec=deepcopy(_TASK),
        card_spec={},
        protocol_profile=_PROFILE,
    )
    result = DesignCompactProcessor().process(_source(), context)
    assert len(result.errors) == 1
    payload = result.errors[0].to_prompt_payload()
    diagnostics = payload.get("compactDiagnostics")
    assert isinstance(diagnostics, list) and len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.get("code") == "COMPACT_LAYOUT_WIDTH_OVERFLOW"
    actual = diagnostic.get("actual")
    assert isinstance(actual, dict)
    assert actual.get("minimumRequiredWidth") == 168
    assert diagnostic.get("fixHint")


@pytest.mark.parametrize("size, canvas_width", [("2x2", 150), ("2x4", 300)])
def test_reference_profile_width_is_used(size: str, canvas_width: int) -> None:
    rows = _basic_rows()
    rows[1] = replace(rows[1], props={"width": "matchParent", "itemMargin": 6})
    rows[2] = replace(rows[2], props={"width": 140, "flexShrink": 0})
    rows[3] = replace(rows[3], props={"width": 140, "flexShrink": 0})
    errors: list[str] = []
    _collect_horizontal_budget_errors(
        rows,
        {"size": size},
        {},
        errors,
        {"sizes": {size: {"width": canvas_width, "height": 150}}},
    )
    assert bool(errors) is (size == "2x2")


def test_unreachable_cycle_does_not_hang_or_pollute_reachable_budget() -> None:
    rows = _basic_rows(width=116)
    rows.extend(
        [
            ComponentRow("detached_a", "Row", {}, ("detached_b",)),
            ComponentRow("detached_b", "Row", {}, ("detached_a",)),
        ]
    )
    assert not _check(rows)


def test_original_text_block_fixture_reports_minimum_width_constraints() -> None:
    path = (
        Path(__file__).parent / "fixtures/compact_horizontal_overflow/text-block-input.jsonl"
    )
    errors = _check(_expanded(path.read_text(encoding="utf-8")))
    by_id = {}
    for diagnostic in errors.records:
        assert not isinstance(diagnostic, str)
        by_id[diagnostic.component_id] = diagnostic
    details = by_id.get("details_content")
    assert details is not None
    assert details.actual.get("minimumRequiredWidth") == 280
    assert details.expected.get("maximumWidth") == 67
    assert details.actual.get("overflow") == 213
    body = by_id.get("body")
    assert body is not None
    assert body.actual.get("minimumRequiredWidth") == 288
    assert body.expected.get("maximumWidth") == 276
    assert set(by_id) == {"body", "details_content"}


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("minimum", [0, 64])
def test_static_minimum_width_is_counted_even_for_weighted_shrinkable_items(
    nested: bool,
    minimum: int,
) -> None:
    rows = _basic_rows()
    for index in (2, 3):
        props = {"layoutWeight": 1, "flexShrink": 1}
        if nested:
            props["constraintSize"] = {"minWidth": minimum, "minHeight": 48}
        else:
            props["minWidth"] = minimum
        rows[index] = replace(rows[index], props=props)
    errors = _check(rows)
    assert bool(errors) is (minimum == 64)
    if errors:
        assert "134vp within 100vp" in errors[0]


def test_nested_width_constraint_overrides_top_level_minimum() -> None:
    rows = _basic_rows()
    for index in (2, 3):
        rows[index] = replace(
            rows[index],
            props={
                "layoutWeight": 1,
                "minWidth": 100,
                "constraintSize": {"minWidth": 40},
            },
        )
    assert not _check(rows)


@pytest.mark.parametrize(
    "constraints",
    [
        {"minWidth": "{{ ${/data/minWidth} }}"},
        {"minWidth": None},
        {"minWidth": True},
        {"minWidth": 64, "maxWidth": 32},
        {"maxWidth": None},
    ],
)
def test_invalid_or_dynamic_constraints_do_not_become_definite_widths(constraints: dict) -> None:
    rows = _basic_rows()
    rows[2] = replace(rows[2], props={**rows[2].props, "constraintSize": constraints})
    assert not _check(rows)


def test_static_maximum_caps_declared_width_without_hiding_descendants() -> None:
    rows = _basic_rows(width=90)
    for index in (2, 3):
        rows[index] = replace(rows[index], props={**rows[index].props, "maxWidth": 40})
    assert not _check(rows)
    rows[2] = replace(rows[2], component_type="Column", children=("fixed",))
    rows.append(ComponentRow("fixed", "Image", {"width": 80, "flexShrink": 0}, ()))
    assert "126vp within 90vp" in _check(rows)[0]


@pytest.mark.parametrize(
    "count, width, overflow", [(2, 276, False), (3, 276, False), (4, 276, True), (4, 280, False)]
)
def test_text_block_public_validation_uses_recipe_minimums(
    count: int,
    width: int,
    overflow: bool,
) -> None:
    items = [{"label": "耳机", "value": "80%"} for _ in range(count)]
    rows = [
        ["root", "Column", {"width": "matchParent"}, ["details"]],
        ["details", "TextBlock", {"width": width, "items": items}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    if overflow:
        with pytest.raises(CompactDslValidationError) as captured:
            validate_compact_dsl(source, task_spec=_TASK, card_spec={})
        assert any(
            item.code == "COMPACT_LAYOUT_WIDTH_OVERFLOW" for item in captured.value.diagnostics
        )
    else:
        assert validate_compact_dsl(source, task_spec=_TASK, card_spec={}).warnings == ()
