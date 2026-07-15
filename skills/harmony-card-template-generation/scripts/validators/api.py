from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .asset_validator import AssetValidator
from .binding_validator import BindingValidator
from .cardspec_validator import CardSpecValidator
from .color_validator import ColorValidator
from .component_validator import ComponentValidator
from .cross_validator import CrossValidator
from .diagnostics import Reporter
from .effective_capability_validator import EffectiveCapabilityValidator
from .expression_validator import ExpressionValidator
from .protocol_validator import ProtocolValidator
from .quality_validator import QualityValidator
from .rule_registry import RuleRegistry
from .source_parser import SourceParser, extract_combined
from .template_validator import TemplateConstraintValidator


STATIC_VALIDATORS = [
    ProtocolValidator(),
    ComponentValidator(),
    CardSpecValidator(),
    ExpressionValidator(),
    AssetValidator(),
    BindingValidator(),
    CrossValidator(),
    ColorValidator(),
    QualityValidator(),
]

EFFECTIVE_VALIDATORS = [
    EffectiveCapabilityValidator(),
]


PIPELINE_BLOCKING_CODES = {
    "DSL_JSON_PARSE_FAILED",
}


@dataclass
class ValidationOptions:
    stage: str = "all"
    max_errors: int = 50
    stop_on_stage_error: bool = False
    skill_dir: Path | None = None
    capabilities_dir: Path | None = None
    template_id: str | None = None


def validate_card(
    *,
    dsl_text: str = "",
    cardspec: dict[str, Any] | str | None = None,
    artifact: dict[str, Any] | str | None = None,
    effective_capabilities: dict[str, Any] | str | None = None,
    options: ValidationOptions | None = None,
) -> Reporter:
    opts = options or ValidationOptions()
    skill_dir = opts.skill_dir or Path(__file__).resolve().parents[2]
    rules = RuleRegistry(skill_dir)
    reporter = Reporter(rules.diagnostics, max_errors=opts.max_errors)

    artifact_value = _parse_jsonish(artifact)
    artifact_value = _unwrap_artifact(artifact_value)
    effective_value = _effective_from_inputs(effective_capabilities, artifact_value)

    resolved_dsl = dsl_text or _artifact_dsl(artifact_value)
    resolved_cardspec = _cardspec_text(cardspec)
    if not resolved_cardspec:
        resolved_cardspec = _artifact_cardspec_text(artifact_value)
    if not resolved_dsl and not resolved_cardspec and isinstance(artifact, str):
        resolved_dsl, resolved_cardspec = extract_combined(artifact)

    context = SourceParser().parse(resolved_dsl, resolved_cardspec, reporter)
    _attach_effective_capabilities(
        context,
        effective_value,
        artifact_value,
        opts.capabilities_dir,
    )
    if not reporter.has_code(*PIPELINE_BLOCKING_CODES):
        run_pipeline(
            context,
            rules,
            reporter,
            opts.stage,
            stop_on_stage_error=opts.stop_on_stage_error,
        )
        if opts.template_id:
            TemplateConstraintValidator(opts.template_id).validate(context, skill_dir, reporter)
    return reporter


def selected_stages(stage: str) -> list[str]:
    if stage == "hard":
        return ["hard"]
    if stage == "semantic":
        return ["hard", "semantic"]
    if stage == "quality":
        return ["hard", "semantic", "quality"]
    return ["hard", "semantic", "quality"]


def run_pipeline(
    context,
    rules,
    reporter: Reporter,
    stage: str,
    *,
    stop_on_stage_error: bool = False,
) -> None:
    validators = STATIC_VALIDATORS + EFFECTIVE_VALIDATORS
    stages = selected_stages(stage)
    for current_stage in stages:
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        for validator in validators:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)


def _parse_jsonish(value: dict[str, Any] | str | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _unwrap_artifact(value: dict[str, Any]) -> dict[str, Any]:
    nested = value.get("artifact")
    if isinstance(nested, dict) and not value.get("genui"):
        return nested
    return value


def _effective_from_inputs(
    effective_capabilities: dict[str, Any] | str | None,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    explicit = _parse_jsonish(effective_capabilities)
    if "effectiveCapabilities" in explicit and isinstance(explicit["effectiveCapabilities"], dict):
        return explicit["effectiveCapabilities"]
    if explicit:
        return explicit
    artifact_effective = artifact.get("effectiveCapabilities")
    return artifact_effective if isinstance(artifact_effective, dict) else {}


def _artifact_dsl(artifact: dict[str, Any]) -> str:
    value = artifact.get("genui")
    return value if isinstance(value, str) else ""


def _cardspec_text(cardspec: dict[str, Any] | str | None) -> str:
    if isinstance(cardspec, dict):
        return json.dumps(cardspec, ensure_ascii=False)
    if isinstance(cardspec, str):
        return cardspec
    return ""


def _artifact_cardspec_text(artifact: dict[str, Any]) -> str:
    value = artifact.get("cardSpec")
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return value
    return ""


def _attach_effective_capabilities(
    context,
    effective: dict[str, Any],
    artifact: dict[str, Any],
    capabilities_dir: Path | None,
) -> None:
    if not effective:
        return
    normalized = {
        "data": _as_list(effective.get("data")),
        "event": _as_list(effective.get("event")),
        "asset": _as_list(effective.get("asset")),
    }
    context.use_effective_capabilities = True
    context.effective_capabilities = normalized
    context.effective_data_capabilities = _resolve_effective_data_capabilities(
        normalized["data"],
        capabilities_dir,
    )
    asset_sources, unresolved = _resolve_effective_asset_sources(
        normalized["asset"],
        artifact,
        capabilities_dir,
    )
    context.effective_asset_sources = asset_sources
    context.unresolved_effective_asset_ids = unresolved


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _resolve_effective_data_capabilities(
    items: list[Any],
    capabilities_dir: Path | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            capability_id = item.get("id") or item.get("capabilityId")
            if isinstance(capability_id, str):
                result[capability_id] = item
    if capabilities_dir is None:
        return result
    data_map = _load_capability_map(capabilities_dir / "data_capabilities.json")
    for item in items:
        capability_id = ""
        if isinstance(item, str):
            capability_id = item
        elif isinstance(item, dict):
            raw_id = item.get("id") or item.get("capabilityId")
            capability_id = raw_id if isinstance(raw_id, str) else ""
        if capability_id and capability_id in data_map:
            result[capability_id] = data_map[capability_id]
    return result


def _resolve_effective_asset_sources(
    items: list[Any],
    artifact: dict[str, Any],
    capabilities_dir: Path | None,
) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    sources: set[str] = set()
    resolved_ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("capabilityId")
            src = item.get("src")
            if isinstance(src, str):
                sources.add(src)
            if isinstance(item_id, str):
                if isinstance(src, str):
                    resolved_ids.add(item_id)
                else:
                    ids.add(item_id)
        elif isinstance(item, str):
            if item.startswith("resources/"):
                sources.add(item)
            else:
                ids.add(item)

    source_by_id: dict[str, str] = {}
    for item in _task_asset_candidates(artifact):
        item_id = item.get("id")
        src = item.get("src")
        if isinstance(item_id, str) and isinstance(src, str):
            source_by_id[item_id] = src

    if capabilities_dir is not None:
        source_by_id.update(_load_asset_capability_map(capabilities_dir))

    for item_id in ids:
        src = source_by_id.get(item_id)
        if src:
            sources.add(src)
            resolved_ids.add(item_id)

    return sources, ids - resolved_ids


def _task_asset_candidates(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    task_spec = artifact.get("taskSpec")
    if not isinstance(task_spec, dict):
        return []
    candidates = task_spec.get("assetCandidates")
    return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []


def _load_asset_capability_map(capabilities_dir: Path) -> dict[str, str]:
    data = _load_capability_list(capabilities_dir / "asset_capabilities.json")
    result: dict[str, str] = {}
    for item in data:
        item_id = item.get("id")
        src = item.get("src")
        if isinstance(item_id, str) and isinstance(src, str):
            result[item_id] = src
    return result


def _load_capability_map(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _load_capability_list(path):
        item_id = item.get("id")
        if isinstance(item_id, str):
            result[item_id] = item
    return result


def _load_capability_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
