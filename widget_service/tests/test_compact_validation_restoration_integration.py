"""恢复规则经公开入口、模型反馈及模板跳过链路的交叉回归。"""

import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from models.artifact import ArtifactMeta, WidgetArtifact
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.diagnostics import DiagnosticCollector
from services.card_validation.compact_validation.semantic.effective import (
    _collect_model_asset_source_errors,
)
from services.card_validation.compact_validation.semantic.layout.assets import (
    _collect_asset_color_errors,
)
from services.card_validation.compact_validation.semantic.numeric_display import (
    _collect_numeric_component_errors,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
)
from services.compact_prompt_loader import assemble_prompts
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.source_artifact_repository import SourceArtifactLoadResult, SourceArtifactRepository

PROMPT_SOURCE = (
    Path(__file__).parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)


def _examples() -> list[tuple[str, dict[str, Any], str]]:
    examples = []
    prompts = assemble_prompts(PROMPT_SOURCE)
    for size in ("2x2", "2x4"):
        document = prompts.get(f"fewshot_{size}")
        assert isinstance(document, str)
        for section in re.split(r"(?m)^## ", document)[1:]:
            identifier = re.search(rf"({size}-V\d\d)", section)
            task = re.search(r"```json\s*\n(.*?)\n```", section, re.S)
            source = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
            assert identifier is not None and task is not None and source is not None
            examples.append((identifier.group(1), json.loads(task.group(1)), source.group(1)))
    return examples


EXAMPLES = _examples()


@pytest.mark.parametrize("identifier,task,source", EXAMPLES, ids=[row[0] for row in EXAMPLES])
def test_restored_rules_accept_every_formal_example(
    identifier: str, task: dict[str, Any], source: str,
) -> None:
    components = []
    for row in parse_compact_dsl_rows(source):
        if isinstance(row, ComponentRow):
            components.append(row)
    original = deepcopy(components)
    errors = DiagnosticCollector()
    _collect_model_asset_source_errors(components, task, errors)
    _collect_asset_color_errors(components, task, errors)
    _collect_numeric_component_errors(components, task, errors)
    assert not errors, (identifier, errors)
    assert components == original


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("undeclared", "COMPACT_ASSET_NOT_ALLOWED"),
        ("missing_tint", "COMPACT_SVG_FILL_COLOR_MISSING"),
        ("plain_status", "COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE"),
    ],
)
def test_formal_layout_error_repairs_without_changing_model_envelope(
    change: str, code: str,
) -> None:
    identifier = "2x2-V05" if change == "plain_status" else "2x2-V12"
    _, task, valid = next(row for row in EXAMPLES if row[0] == identifier)
    task = deepcopy(task)
    rows = [json.loads(line) for line in valid.splitlines() if line.strip()]
    original_type = "EmphasizedData" if change == "plain_status" else "ProgressCircle"
    changed = next(row for row in rows if len(row) >= 3 and row[1] == original_type)
    original_props = deepcopy(changed[2])
    if change == "plain_status":
        changed[2]["value"] = "正常"
        changed[2].pop("unit", None)
    elif change == "missing_tint":
        changed[2].pop("fillColor", None)
    else:
        changed[2]["icon"] = "resources/not_in_candidates.svg"
    invalid = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            invalid, task_spec=task, card_spec={"suggestSize": "2x2"},
            enforce_model_component_types=True, layout_scope="S-plan-guided",
        )
    error = captured.value
    diagnostic = next(item for item in error.diagnostics if item.code == code)
    assert diagnostic.component_id == changed[0]
    assert diagnostic.property_path == ("/value" if change == "plain_status" else "/icon")
    assert diagnostic.source_line is not None
    assert diagnostic.evidence_source != "expanded"
    assert diagnostic.fix_hint
    assert error.args == (str(error),)
    issues = DesignCompactProcessor._validation_failure(invalid, error.errors, groups=error.groups)
    quality = [item.to_prompt_payload() for item in issues.errors]
    before = deepcopy(quality)
    prompt = PromptBuilder().build_repair(
        [{"role": "system", "content": "合同"}, {"role": "user", "content": "{}"}],
        invalid, quality,
    )
    content = prompt[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    model_errors = payload.get("qualityErrors")
    assert isinstance(model_errors, list) and model_errors
    assert all(item.get("code") == "COMPACT_DSL_VALIDATION_FAILED" for item in model_errors)
    assert all(item.get("stage") == "validation" for item in model_errors)
    assert "compactDiagnostics" not in content
    assert code in content and diagnostic.fix_hint in content
    assert quality == before
    changed[2] = original_props
    repaired = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = validate_compact_dsl(
        repaired, task_spec=task, card_spec={"suggestSize": "2x2"},
        enforce_model_component_types=True, layout_scope="S-plan-guided",
    )
    assert result.warnings == ()


def test_template_skip_still_bypasses_all_restored_rules() -> None:
    source = '\n'.join(
        ['["root","Column",{},["status"]]', '["status","EmphasizedData",{"value":"正常"}]']
    )
    protocol = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    context = DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"},
        task_spec={"size": "2x2", "appVersion": "11.7.5.208", "dataModelSchema": {"data": {}}},
        protocol_profile=protocol,
    )
    processor = DesignCompactProcessor()
    checked = processor.process(source, context)
    assert any("NUMERIC_COMPONENT_MISUSE" in str(item.prompt_context) for item in checked.errors)
    skipped = processor.process(source, replace(context, skip_compact_dsl_validation=True))
    assert not skipped.errors
    assert skipped.standard_dsl


ICON = "resources/base/media/drop_1.svg"
EVENT = {"call": "clickToDeeplink", "args": {"uri": "settings://battery"}}


def _icon_card(kind: str, icon: str = ICON, *, native: bool = False) -> str:
    props: dict[str, Any]
    if kind in {"PillButton", "CircleButton", "CardButton"}:
        props = {"label": "设置", "icon": icon, "onClick": [deepcopy(EVENT)]}
        if kind == "CircleButton":
            props.pop("label")
            props["accessibility"] = {"label": "设置"}
        if kind == "CardButton" and not native:
            props["fillColor"] = "#FF1F4799"
    elif kind == "ProgressCircleSingle":
        props = {
            "icon": icon, "value": 50, "total": 100, "displayValue": "50%", "label": "电量",
            "color": "#FF1F4799", "backgroundColor": "#331F4799",
        }
    elif kind == "ProgressCircle":
        props = {
            "icon": icon, "externalText": "50%", "accessibility": {"label": "电量"},
            "width": 52, "height": 68, "color": "#FF1F4799", "backgroundColor": "#331F4799",
        }
        if not native:
            props["fillColor"] = "#FF1F4799"
    elif kind == "InfoBlock":
        props = {
            "primaryText": "50", "secondaryText": "电量", "backgroundColor": "#99FFFFFF",
            "variant": "slot",
            "visual": {"type": "icon", "icon": icon},
        }
        visual = props.get("visual")
        assert isinstance(visual, dict)
        if native:
            visual["color"] = "native"
    else:
        assert kind == "NumericRatioStack"
        items = []
        for value in (20, 30, 50):
            items.append({"icon": icon, "value": value, "unit": "%"})
        props = {"items": items, "direction": "column", "fillColor": "#FF1F4799"}
    rows = [["root", "Column", {}, ["visual"]], ["visual", kind, props]]
    if kind == "CircleButton":
        rows[0] = ["root", "Column", {}, ["slot"]]
        rows.append([
            "slot", "Stack", {"width": 40, "height": 40, "alignContent": "center"}, ["visual"],
        ])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _icon_task(native: bool = False) -> dict[str, Any]:
    return {
        "size": "2x4", "dataModelSchema": {"data": {}}, "eventCandidates": [deepcopy(EVENT)],
        "assetCandidates": [{"src": ICON, "description": "保留原色" if native else "单色图标"}],
    }


@pytest.mark.parametrize(
    ("kind", "native"),
    [
        ("PillButton", False), ("CircleButton", False), ("ProgressCircleSingle", False),
        ("InfoBlock", False), ("InfoBlock", True), ("NumericRatioStack", False),
        ("ProgressCircle", False),
        ("CardButton", False),
    ],
)
def test_validated_components_keep_automatic_explicit_and_native_colors(
    kind: str, native: bool,
) -> None:
    source = _icon_card(kind, native=native)
    task = _icon_task(native)
    size = "2x2" if kind == "CircleButton" else "2x4"
    task["size"] = size
    validate_compact_dsl(
        source, task_spec=task, card_spec={"suggestSize": size},
        enforce_model_component_types=True,
    )
    converted = convert_compact_dsl_to_a2ui(source, size=size)
    messages = [json.loads(line) for line in converted.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    icons = [item for item in components if item.get("component") == "Image"]
    assert icons
    for icon in icons:
        assert icon.get("src") == ICON
        styles = icon.get("styles")
        assert isinstance(styles, dict)
        assert ("fillColor" not in styles) is native


@pytest.mark.parametrize("kind", ["InfoBlock", "ProgressCircle", "CardButton"])
def test_native_bitmap_still_preserves_original_color(kind: str) -> None:
    bitmap = "resources/base/media/photo.png"
    source = _icon_card(kind, icon=bitmap, native=True)
    task = _icon_task(native=True)
    task["assetCandidates"] = [{"src": bitmap, "description": "保留原色"}]
    validate_compact_dsl(
        source, task_spec=task, card_spec={"suggestSize": "2x4"},
        enforce_model_component_types=True,
    )
    converted = convert_compact_dsl_to_a2ui(source, size="2x4")
    messages = [json.loads(line) for line in converted.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    icons = [item for item in components if item.get("component") == "Image"]
    assert icons
    for icon in icons:
        assert icon.get("src") == bitmap
        styles = icon.get("styles")
        assert isinstance(styles, dict)
        assert "fillColor" not in styles


@pytest.mark.parametrize("kind", ["InfoBlock", "NumericRatioStack"])
def test_source_artifact_restores_nested_icons_before_new_validation(kind: str) -> None:
    address = "https://assets.example.test/drop.svg"
    token = _icon_card(kind, icon=address)
    artifact = WidgetArtifact(
        genui="", cardSpec={"suggestSize": "2x4"}, taskSpec=_icon_task(),
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-6.0", createdAt=0,
        ),
    )
    original = artifact.model_copy(deep=True)
    source = SourceArtifactLoadResult(
        artifact=artifact, design_token=token, artifact_digest="original-digest", url_hash="hash",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    restored = SourceArtifactRepository.restore_asset_paths(
        source, {ICON: address}, restore_genui=False,
    )
    assert restored.design_token is not None
    assert address not in restored.design_token
    assert restored.artifact_digest == source.artifact_digest
    assert source.artifact == original
    assert source.design_token == token
    validate_compact_dsl(
        restored.design_token, task_spec=restored.artifact.taskSpec,
        card_spec=restored.artifact.cardSpec, enforce_model_component_types=True,
    )


@pytest.mark.parametrize(
    ("kind", "property_path"),
    [("InfoBlock", "/visual/icon"), ("NumericRatioStack", "/items/1/icon")],
)
def test_nested_asset_diagnostic_points_to_original_property(
    kind: str, property_path: str,
) -> None:
    rows = [json.loads(line) for line in _icon_card(kind).splitlines()]
    props = rows[1][2]
    if kind == "InfoBlock":
        visual = props.get("visual")
        assert isinstance(visual, dict)
        visual["icon"] = "resources/unknown.svg"
    else:
        items = props.get("items")
        assert isinstance(items, list)
        items[1]["icon"] = "resources/unknown.svg"
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            source, task_spec=_icon_task(), card_spec={"suggestSize": "2x4"},
            enforce_model_component_types=True,
        )
    assert len(captured.value.diagnostics) == 1
    issue = captured.value.diagnostics[0]
    assert issue.code == "COMPACT_ASSET_NOT_ALLOWED"
    assert issue.component_id == "visual"
    assert issue.property_path == property_path
    assert issue.source_line == 2


@pytest.mark.parametrize("kind", ["ProgressCircle", "CardButton"])
@pytest.mark.parametrize("color", [None, "not-a-color"])
def test_existing_color_contract_still_rejects_invalid_present_colors(
    kind: str, color: Any,
) -> None:
    rows = [json.loads(line) for line in _icon_card(kind).splitlines()]
    rows[1][2]["fillColor"] = color
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with pytest.raises(CompactDslValidationError, match="fillColor") as captured:
        validate_compact_dsl(
            source, task_spec=_icon_task(), card_spec={"suggestSize": "2x4"},
            enforce_model_component_types=True,
        )
    assert captured.value.__cause__ is not None
    assert not captured.value.diagnostics


@pytest.mark.parametrize("reading_id", ["reading", "template_root"])
def test_restored_rules_report_independent_errors_and_recheck_partial_repairs(
    reading_id: str,
) -> None:
    rows = [json.loads(line) for line in _icon_card("ProgressCircle").splitlines()]
    rows[0][3].append(reading_id)
    rows[1][2].pop("fillColor")
    rows.append([reading_id, "EmphasizedData", {"value": "正常"}])

    def validate() -> None:
        source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        validate_compact_dsl(
            source, task_spec=_icon_task(), card_spec={"suggestSize": "2x4"},
            enforce_model_component_types=True,
        )

    with pytest.raises(CompactDslValidationError) as captured:
        validate()
    assert [issue.code for issue in captured.value.diagnostics] == [
        "COMPACT_SVG_FILL_COLOR_MISSING", "COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE",
    ]
    rows[1][2]["fillColor"] = "#FF1F4799"
    with pytest.raises(CompactDslValidationError) as remaining:
        validate()
    assert [issue.code for issue in remaining.value.diagnostics] == [
        "COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE",
    ]
    rows[2][2]["value"] = 50
    validate()
