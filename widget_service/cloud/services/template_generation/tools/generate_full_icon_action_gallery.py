"""枚举全部 Full 模板，生成独立于运行时白名单的图标叠放验收画廊。"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from models.generation import TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    _expand_health_metric_generic_template,
    _instantiate_blueprint,
    _serialize_effective_document,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.full_icon_action_policy import template_digest
from services.template_generation.engine.cardplan.fusion_ball_background import (
    apply_content_safe_inset,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    _binding_placeholder,
    _build_data_schema,
    _preview_root,
    _preview_theme,
    _template_parameters,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui

LAYOUT_ID = "FullIconActionLayout@1"
ACTION_ID = "IconAction@1"
STATES = ("standard", "long-text", "optional-assets-off")


def _stress_text(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _stress_text(item)
        return
    if not isinstance(value, dict):
        return
    sample = value.get("sampleValue")
    if value.get("type") == "string" and isinstance(sample, str):
        value["sampleValue"] = sample + "较长内容用于排版边界检查"
    for child in value.values():
        _stress_text(child)


def _boundary_values(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _boundary_values(item)
        return
    if not isinstance(value, dict):
        return
    value_type = value.get("type")
    if value_type == "boolean":
        value["sampleValue"] = not value.get("sampleValue", False)
    elif value_type == "integer":
        value["sampleValue"] = 100
    elif value_type == "number":
        value["sampleValue"] = 100.0
    for child in value.values():
        _boundary_values(child)


def render_case(registry: CardPlanRegistry, template_id: str, state: str) -> str:
    """展开真实布局与动作蓝图；仅省略独立验收按钮的事件处理器。"""
    definition = registry.require_template(template_id)
    schema = _build_data_schema(definition)
    params = _template_parameters(definition)
    properties = definition.variants[0].parameters_schema.get("properties", {})
    required = definition.variants[0].parameters_schema.get("required", [])
    if state not in (*STATES, "boundary-values"):
        raise ValueError(f"Unknown audit state: {state}")
    if state == "long-text":
        _stress_text(schema)
        for name, value in tuple(params.items()):
            if name.endswith("Path") or name == "actionId":
                continue
            if properties.get(name, {}).get("type") == "string":
                if not value.startswith("resources/"):
                    params[name] = value + "较长内容用于排版边界检查"
    elif state == "optional-assets-off":
        for name, value in tuple(params.items()):
            if name not in required and value.startswith("resources/"):
                params.pop(name)
    elif state == "boundary-values":
        _boundary_values(schema)
    task = TaskSpec(userQuery="图标叠放排版验收", size="2x2", dataModelSchema=schema)
    theme = _preview_theme(definition, registry)
    bindings = {}
    for name, binding in definition.bindings.items():
        bindings[name] = _binding_placeholder(definition, binding)
    if definition.business_id == "GenericMetricOverview":
        content = _expand_health_metric_generic_template(
            template_id, params, task_spec=task,
            provider_binding_roots={"GetHealthAndSportSummary": (definition.data_domain,)},
            theme_values=theme.reference_values,
        )
    else:
        content = _instantiate_blueprint(
            definition.variants[0].root, params, bindings, theme.reference_values,
        )
    content = _strip_advanced_component_markers(content)
    action = _instantiate_blueprint(
        registry.require_template(ACTION_ID).variants[0].root,
        {"actionId": "preview-only", "icon": "resources/base/media/icon_right.svg"},
        {}, theme.reference_values,
    )
    action_props = dict(action.values[0])
    action_props.pop("onClick", None)
    action_props["_id"] = "audit_icon_action"
    action = replace(action, values=(action_props,))
    layout = _instantiate_blueprint(
        registry.require_template(LAYOUT_ID).variants[0].root,
        {}, {}, theme.reference_values, spread_children=(content, action),
    )
    layout = _strip_advanced_component_markers(layout)
    root = _preview_root(layout, 136, theme.root_style, fill_available_height=True)
    root = apply_content_safe_inset(root, size="2x2")
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    a2ui = convert_tersel_to_a2ui(
        _serialize_effective_document(root, task, True), size="2x2",
        protocol_profile=profile, task_spec=task.model_dump(mode="json"),
    )
    messages = [json.loads(line) for line in a2ui.splitlines() if line.strip()]
    return json.dumps(messages, ensure_ascii=False, indent=2) + "\n"


def write_gallery(output: Path) -> dict[str, Any]:
    registry = CardPlanRegistry(enable_fusion_ball=True)
    output.mkdir(parents=True, exist_ok=True)
    (output / "cards").mkdir(exist_ok=True)
    cases = []
    template_ids = []
    for template_id in sorted(registry.provider_template_ids):
        definition = registry.require_template(template_id)
        if definition.business_id and provider_template_layout_kind(template_id) == "Full":
            template_ids.append(template_id)
    for index, template_id in enumerate(template_ids, 1):
        definition = registry.require_template(template_id)
        sizes = definition.variants[0].supported_card_sizes
        for state_index, state in enumerate(STATES):
            identity = f"FI{index:03d}-{state_index}"
            case = {
                "caseId": identity, "cardSize": "2x2", "providerId": "full-icon-audit",
                "providerName": "Full 图标叠放验收", "businessId": definition.business_id,
                "businessName": definition.description, "scenarioId": state,
                "scenarioName": state, "expectedLayout": LAYOUT_ID,
                "expectedTemplateSuffix": "Full", "targetTemplateId": template_id,
                "templateDigest": template_digest(definition),
                "partnerTemplateId": "", "generationStatus": "deterministic-preview",
                "status": "not_generated", "a2uiFile": "", "errorMessage": "",
                "artifactDigest": "", "visualStatus": "pending",
            }
            if sizes and "2x2" not in sizes:
                case.update(status="not_applicable", errorMessage="模板仅支持宽卡")
            else:
                try:
                    source = render_case(registry, template_id, state)
                    filename = f"cards/{identity}.json"
                    (output / filename).write_text(source, encoding="utf-8")
                    case.update(status="success", a2uiFile=filename,
                                artifactDigest=hashlib.sha256(source.encode()).hexdigest())
                except (ValueError, RuntimeError) as exc:
                    case.update(status="failed", errorMessage=f"{type(exc).__name__}: {exc}")
            cases.append(case)
    counts = {}
    for case in cases:
        status = case.get("status")
        counts[status] = counts.get(status, 0) + 1
    manifest = {
        "schemaVersion": "provider-template-gallery-output/2", "templateCount": len(template_ids),
        "counts": counts, "layoutTemplateId": LAYOUT_ID, "actionTemplateId": ACTION_ID,
        "layoutDigest": template_digest(registry.require_template(LAYOUT_ID)),
        "actionDigest": template_digest(registry.require_template(ACTION_ID)),
        "providers": [{"providerId": "full-icon-audit", "providerSlug": "full-icon-audit",
                       "providerName": "Full 图标叠放验收", "cases": cases}],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = write_gallery(args.output)
    print(json.dumps(manifest.get("counts"), ensure_ascii=False))


if __name__ == "__main__":
    main()
