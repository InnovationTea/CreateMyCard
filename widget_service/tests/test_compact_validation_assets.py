"""恢复素材约束时保留高阶组件自动着色、模板边界及旧背景行为。"""

import json
from typing import Any

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation import api
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    DiagnosticCollector,
)
from services.card_validation.compact_validation.semantic.effective import (
    _collect_asset_source_errors,
    _collect_model_asset_source_errors,
)
from services.card_validation.compact_validation.semantic.layout.assets import (
    _collect_asset_color_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow

ICON = "resources/device.svg"
COLOR = "#FF112233"


def _row(kind: str, props: dict[str, Any]) -> ComponentRow:
    return ComponentRow("visual", kind, props, ())


def _task(candidates: Any) -> dict[str, Any]:
    return {"size": "2x4", "dataModelSchema": {"data": {}}, "assetCandidates": candidates}


def _diagnostics(errors: DiagnosticCollector) -> list[CompactDiagnostic]:
    return [record for record in errors.records if isinstance(record, CompactDiagnostic)]


@pytest.mark.parametrize(
    ("kind", "props", "path"),
    [
        ("ProgressCircle", {"icon": ICON}, "/icon"),
        ("ProgressCircleSingle", {"icon": ICON}, "/icon"),
        ("PillButton", {"icon": ICON}, "/icon"),
        ("CircleButton", {"icon": ICON}, "/icon"),
        ("CardButton", {"icon": ICON}, "/icon"),
        ("SingleLineTitle", {"icon": ICON}, "/icon"),
        ("InfoBlock", {"icon": ICON}, "/icon"),
        ("InfoBlock", {"visual": {"type": "icon", "icon": ICON}}, "/visual/icon"),
        (
            "InfoBlock",
            {"visual": {"type": "progressCircle", "icon": ICON}},
            "/visual/icon",
        ),
        ("NumericRatioStack", {"items": [{"icon": ICON, "value": 3}]}, "/items/0/icon"),
        ("Image", {"src": ICON}, "/src"),
    ],
)
def test_registered_original_asset_properties_are_checked(
    kind: str, props: dict[str, Any], path: str
) -> None:
    errors = DiagnosticCollector()
    _collect_model_asset_source_errors([_row(kind, props)], _task([]), errors)
    diagnostics = _diagnostics(errors)
    assert len(diagnostics) == 1
    issue = diagnostics[0]
    assert issue.code == "COMPACT_ASSET_NOT_ALLOWED"
    assert issue.category == "effective"
    assert issue.property_path == path
    assert issue.actual.get("src") == ICON
    assert issue.fix_hint is None
    allowed_errors: list[str] = []
    _collect_model_asset_source_errors([_row(kind, props)], _task([{"src": ICON}]), allowed_errors)
    assert allowed_errors == []


@pytest.mark.parametrize("candidates", [None, {}, "not-a-list"])
def test_missing_or_malformed_candidate_list_keeps_compatibility(candidates: Any) -> None:
    rows = [_row("ProgressCircle", {"icon": ICON})]
    errors: list[str] = []
    _collect_model_asset_source_errors(rows, _task(candidates), errors)
    _collect_asset_color_errors(rows, _task(candidates), errors)
    assert errors == []
    _collect_model_asset_source_errors(rows, {}, errors)
    _collect_asset_color_errors(rows, {}, errors)
    assert errors == []


def test_malformed_candidates_are_ignored_without_coercing_sources() -> None:
    errors: list[str] = []
    candidates = [None, 12, {"src": 42}, {"src": ICON}]
    _collect_model_asset_source_errors([_row("Image", {"src": ICON})], _task(candidates), errors)
    assert errors == []
    _collect_model_asset_source_errors([_row("Image", {"src": "42"})], _task(candidates), errors)
    assert len(errors) == 1


@pytest.mark.parametrize("value", [None, 12, False, [], {}, "", "  ", " {{ $icon }}"])
def test_invalid_types_and_expressions_keep_existing_contract_owner(value: Any) -> None:
    rows = [_row("ProgressCircle", {"icon": value})]
    errors: list[str] = []
    _collect_model_asset_source_errors(rows, _task([]), errors)
    _collect_asset_color_errors(rows, _task([]), errors)
    assert errors == []


def test_unknown_fields_and_background_are_not_model_icon_references() -> None:
    rows = [
        _row("Column", {"icon": ICON, "backgroundImage": ICON}),
        _row("UnknownComponent", {"icon": ICON, "src": ICON}),
        _row("EmphasisText", {"mainText": ICON}),
        _row("InfoBlock", {"visual": [ICON]}),
        _row("NumericRatioStack", {"items": {"icon": ICON}}),
        _row("NumericRatioStack", {"items": [None, {"icon": 5}]}),
    ]
    errors: list[str] = []
    _collect_model_asset_source_errors(rows, _task([]), errors)
    assert errors == []


def test_nested_asset_errors_keep_input_order_and_original_paths() -> None:
    rows = [_row("NumericRatioStack", {"items": [{"icon": "b.svg"}, {"icon": "a.svg"}]})]
    errors = DiagnosticCollector()
    _collect_model_asset_source_errors(rows, _task([{"src": "allowed.svg"}]), errors)
    diagnostics = _diagnostics(errors)
    assert [issue.property_path for issue in diagnostics] == ["/items/0/icon", "/items/1/icon"]
    assert [issue.actual.get("src") for issue in diagnostics] == ["b.svg", "a.svg"]
    assert ".props.items[0].icon:" in errors[0]


def test_background_asset_rule_keeps_legacy_message_and_scope() -> None:
    rows = [
        _row("Image", {"src": "unknown.svg"}),
        ComponentRow("root", "Column", {"backgroundImage": "background.svg"}, ()),
    ]
    errors = DiagnosticCollector()
    _collect_asset_source_errors(rows, _task([]), errors)
    assert errors == [
        "component root.props.backgroundImage: asset must use an original src "
        "from TaskSpec.assetCandidates."
    ]
    diagnostic = _diagnostics(errors)[0]
    assert diagnostic.property_path == "/backgroundImage"
    assert diagnostic.actual == {"property": "backgroundImage", "src": "background.svg"}


@pytest.mark.parametrize("kind", ["ProgressCircle", "CardButton"])
@pytest.mark.parametrize("description", [None, "", "默认黑色单色 SVG", "可染色图标"])
def test_explicit_tint_contract_reports_missing_fill_color(kind: str, description: Any) -> None:
    errors = DiagnosticCollector()
    _collect_asset_color_errors(
        [_row(kind, {"icon": ICON})], _task([{"src": ICON, "description": description}]), errors
    )
    diagnostics = _diagnostics(errors)
    assert len(diagnostics) == 1
    issue = diagnostics[0]
    assert issue.code == "COMPACT_SVG_FILL_COLOR_MISSING"
    assert issue.category == "layout"
    assert issue.property_path == "/icon"
    assert issue.expected.get("requiredProperty") == "fillColor"
    assert issue.actual.get("fillColorPresent") is False
    assert issue.fix_hint is None


@pytest.mark.parametrize("description", ["不可染色", "保留原色", "多色", "品牌原色"])
@pytest.mark.parametrize("kind", ["ProgressCircle", "CardButton"])
def test_svg_description_does_not_disable_explicit_tint_contract(
    kind: str,
    description: str,
) -> None:
    errors = DiagnosticCollector()
    _collect_asset_color_errors(
        [_row(kind, {"icon": ICON})], _task([{"src": ICON, "description": description}]), errors
    )
    diagnostics = _diagnostics(errors)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "COMPACT_SVG_FILL_COLOR_MISSING"


@pytest.mark.parametrize("source", ["resources/picture.png", "resources/photo.PNG"])
def test_png_does_not_require_fill_color(source: str) -> None:
    errors: list[str] = []
    _collect_asset_color_errors(
        [_row("ProgressCircle", {"icon": source})], _task([{"src": source}]), errors
    )
    assert errors == []


@pytest.mark.parametrize("fill_color", [COLOR, None, "invalid-color"])
def test_present_fill_color_is_validated_by_component_contract(fill_color: Any) -> None:
    errors: list[str] = []
    _collect_asset_color_errors(
        [_row("ProgressCircle", {"icon": ICON, "fillColor": fill_color})],
        _task([{"src": ICON}]),
        errors,
    )
    assert errors == []


@pytest.mark.parametrize(
    ("kind", "props"),
    [
        ("ProgressCircleSingle", {"icon": ICON}),
        ("PillButton", {"icon": ICON}),
        ("CircleButton", {"icon": ICON}),
        ("SingleLineTitle", {"icon": ICON}),
        ("InfoBlock", {"icon": ICON}),
        ("InfoBlock", {"visual": {"type": "icon", "icon": ICON, "color": "native"}}),
        ("NumericRatioStack", {"items": [{"icon": ICON}]}),
        ("Image", {"src": ICON}),
    ],
)
def test_automatic_native_and_existing_required_color_contracts_are_unchanged(
    kind: str, props: dict[str, Any]
) -> None:
    errors: list[str] = []
    _collect_asset_color_errors([_row(kind, props)], _task([{"src": ICON}]), errors)
    assert errors == []


def test_unknown_svg_is_only_an_asset_scope_error() -> None:
    rows = [_row("ProgressCircle", {"icon": ICON})]
    errors = DiagnosticCollector()
    _collect_model_asset_source_errors(rows, _task([]), errors)
    _collect_asset_color_errors(rows, _task([]), errors)
    assert [issue.code for issue in _diagnostics(errors)] == ["COMPACT_ASSET_NOT_ALLOWED"]


def _source(kind: str, props: dict[str, Any]) -> str:
    rows = [["root", "Column", {}, ["visual"]], ["visual", kind, props]]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize(
    ("candidates", "code"),
    [([], "COMPACT_ASSET_NOT_ALLOWED"), ([{"src": ICON}], "COMPACT_SVG_FILL_COLOR_MISSING")],
)
def test_original_asset_errors_stop_before_expansion_and_keep_source_location(
    candidates: list[Any], code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("模型素材错误必须在展开前反馈")

    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden)
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            _source("ProgressCircle", {"icon": ICON}),
            task_spec=_task(candidates),
            card_spec={},
        )
    diagnostics = captured.value.diagnostics
    assert len(diagnostics) == 1
    issue = diagnostics[0]
    assert issue.code == code
    assert issue.component_id == "visual"
    assert issue.property_path == "/icon"
    assert issue.source_line == 2


@pytest.mark.parametrize(
    "original_source",
    [
        _source("ProgressCircle", {"icon": "resources/previous.svg"}),
        "unavailable original JSONL",
        _source("Image", {"src": ICON}),
    ],
)
def test_rewritten_source_does_not_report_unproven_property_location(
    original_source: str,
) -> None:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            _source("ProgressCircle", {"icon": ICON}),
            task_spec=_task([]),
            card_spec={},
            original_source=original_source,
        )
    issue = captured.value.diagnostics[0]
    assert issue.code == "COMPACT_ASSET_NOT_ALLOWED"
    assert issue.property_path is None
    assert issue.actual.get("src") == ICON


def test_internal_generated_image_is_not_checked_as_a_model_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def expanded(*_args: Any, **_kwargs: Any) -> list[ComponentRow]:
        return [
            ComponentRow("root", "Column", {}, ("internal_icon",)),
            ComponentRow("internal_icon", "Image", {"src": "runtime/internal.svg"}, ()),
        ]

    monkeypatch.setattr(api, "expand_high_level_component_rows", expanded)
    result = validate_compact_dsl(
        _source("EmphasisText", {"mainText": "完整内容"}),
        task_spec=_task([]),
        card_spec={},
    )
    assert result.warnings == ()
