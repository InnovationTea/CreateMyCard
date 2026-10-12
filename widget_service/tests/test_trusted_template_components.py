"""模板来源、组件范围和 Compact 校验回归。"""

import json
from dataclasses import replace

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
    repair_compact_dsl_binding_paths,
    repair_compact_dsl_safe_structure,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def _source(component_type: str, props: dict) -> str:
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"},
         ["template_root"]],
        ["template_root", "Column", {}, ["body"]],
        ["body", component_type, props],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _context() -> DslProcessingContext:
    return DslProcessingContext(
        size="2x2",
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        task_spec={
            "appVersion": "11.7.7.300",
            "size": "2x2",
            "dataModelSchema": {"data": {}},
            "assetCandidates": [{"src": "resources/battery.svg"}],
            "eventCandidates": [],
        },
        protocol_profile={"version": "v0.9"},
    )


@pytest.mark.parametrize(("component_type", "props"), [
    ("Image", {"src": "resources/battery.svg", "width": 24, "height": 24,
               "fillColor": "#FF1F4799"}),
    ("Divider", {"height": 1}),
    ("Progress", {"value": 50, "total": 100, "height": 8}),
    ("Button", {"label": "按钮", "height": 36}),
])
def test_internal_components_require_explicit_permission(component_type: str, props: dict) -> None:
    source = _source(component_type, props)
    context = _context()
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        parse_compact_dsl_rows(source)
    repaired = repair_compact_dsl_binding_paths(
        source, task_spec=context.task_spec, card_spec=context.card_spec,
        allow_internal_components=True,
    )
    standard = convert_compact_dsl_to_a2ui(
        repaired, size=context.size, allow_internal_components=True,
    )
    assert component_type in standard
    with pytest.raises(CompactDslValidationError, match="converter-internal"):
        validate_compact_dsl(
            source, task_spec=context.task_spec, card_spec=context.card_spec,
            allow_internal_components=True, enforce_model_component_types=True,
        )


def test_skipping_validation_does_not_grant_template_permission() -> None:
    source = _source("Image", {"src": "resources/battery.svg", "width": 24, "height": 24,
                               "fillColor": "#FF1F4799"})
    context = replace(_context(), skip_compact_dsl_validation=True)
    denied = DesignCompactProcessor().process(source, context)
    assert denied.errors
    assert "unsupported component type Image" in denied.errors[0].message
    # 模板来源由处理上下文提供。
    allowed = DesignCompactProcessor().process(
        source, replace(context, trusted_template_source=True),
    )
    assert not allowed.errors
    assert '"Image"' in allowed.standard_dsl


def test_trusted_template_can_still_run_compact_validation() -> None:
    source = _source("Divider", {"height": 1})
    result = DesignCompactProcessor().process(
        source, replace(_context(), trusted_template_source=True),
    )
    assert not result.errors
    assert '"Divider"' in result.standard_dsl


def test_trusted_template_preserves_compiled_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_recomposition(*_args, **_kwargs):
        pytest.fail("模板直接使用编译后的布局。")

    monkeypatch.setattr(
        "services.generation_pipeline.recompose_small_card", unexpected_recomposition,
    )
    result = DesignCompactProcessor().process(
        _source("Divider", {"height": 1}),
        replace(_context(), trusted_template_source=True, layout_scope="all"),
    )
    assert not result.errors


def test_trusted_template_processor_still_rejects_overflow() -> None:
    result = DesignCompactProcessor().process(
        _source("Divider", {"height": 200}),
        replace(_context(), trusted_template_source=True, layout_scope="all"),
    )
    assert result.errors
    assert any("overflows" in error.message for error in result.errors)


@pytest.mark.parametrize(("component_type", "props", "error"), [
    ("UnknownWidget", {}, "unsupported component type"),
    ("Image", {"_visualRecipe": "fake"}, "reserved"),
])
def test_trusted_permission_does_not_bypass_parser_guards(
    component_type: str, props: dict, error: str,
) -> None:
    with pytest.raises(CompactDslConversionError, match=error):
        parse_compact_dsl_rows(_source(component_type, props), allow_internal_components=True)


def test_trusted_permission_does_not_disable_height_budget() -> None:
    with pytest.raises(CompactDslValidationError, match="overflows"):
        validate_compact_dsl(
            _source("Divider", {"height": 200}),
            task_spec=_context().task_spec, card_spec=_context().card_spec,
            allow_internal_components=True,
        )


def test_trusted_permission_does_not_disable_background_asset_allowlist() -> None:
    with pytest.raises(CompactDslValidationError, match="assetCandidates"):
        validate_compact_dsl(
            _source("Divider", {"backgroundImage": "resources/undeclared.svg"}),
            task_spec=_context().task_spec, card_spec=_context().card_spec,
            allow_internal_components=True,
        )


@pytest.mark.parametrize(("component_type", "props"), [
    ("Image", {"src": "resources/battery.svg", "width": 24, "height": 24,
               "fillColor": "#FF1F4799"}),
    ("Divider", {"height": 1}),
    ("Progress", {"value": 50, "total": 100, "height": 8}),
    ("Button", {"label": "按钮", "height": 36}),
])
@pytest.mark.parametrize("with_orphan", [False, True])
def test_safe_structure_keeps_template_permission_during_orphan_repair(
    component_type: str, props: dict, with_orphan: bool,
) -> None:
    source = _source(component_type, props)
    if with_orphan:
        source += '\n["orphan", "SecondaryBody", {"items": [{"value": "孤立节点"}]}]'
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        repair_compact_dsl_safe_structure(source, size="2x2")
    repaired = repair_compact_dsl_safe_structure(
        source, size="2x2", allow_internal_components=True,
    )
    if not with_orphan:
        assert repaired == source
    rows = parse_compact_dsl_rows(repaired, allow_internal_components=True)
    assert [row.component_id for row in rows] == ["root", "template_root", "body"]
    result = DesignCompactProcessor().process(
        source, replace(_context(), trusted_template_source=True),
    )
    assert not result.errors
    assert "orphan" not in result.standard_dsl
    assert f'"{component_type}"' in result.standard_dsl


def test_safe_structure_template_permission_preserves_unknown_component_error() -> None:
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        repair_compact_dsl_safe_structure(
            _source("UnknownWidget", {}), size="2x2", allow_internal_components=True,
        )
