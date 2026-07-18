"""Validator pipeline orchestration.

Owns the static list of built-in validators and the stage/short-circuit logic.
``validators`` are grouped by responsibility so it is obvious at a glance which
subsystem a given validator belongs to.
"""

from __future__ import annotations

from .aesthetic import QualityValidator
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


STATIC_VALIDATORS = [
    ProtocolValidator(),
    ComponentValidator(),
    CardSpecValidator(),
    ExpressionValidator(),
    AssetValidator(),
    BindingValidator(),
    CrossValidator(),
    ColorValidator(),
]

EFFECTIVE_VALIDATORS = [
    EffectiveCapabilityValidator(),
]

AESTHETIC_VALIDATORS = [
    QualityValidator(),
]


PIPELINE_BLOCKING_CODES = {
    "DSL_JSON_PARSE_FAILED",
}


def selected_stages(stage: str) -> list[str]:
    if stage == "hard":
        return ["hard"]
    if stage == "semantic":
        return ["hard", "semantic"]
    # "quality" and "all" both run every stage.
    return ["hard", "semantic", "quality"]


def run_pipeline(
    context,
    rules,
    reporter: Reporter,
    stage: str,
    *,
    stop_on_stage_error: bool = False,
    enable_aesthetic: bool = False,
) -> None:
    validators = list(STATIC_VALIDATORS) + list(EFFECTIVE_VALIDATORS)
    if enable_aesthetic:
        validators.extend(AESTHETIC_VALIDATORS)
    for current_stage in selected_stages(stage):
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        for validator in validators:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)
