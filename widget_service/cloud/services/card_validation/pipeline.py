# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Validator pipeline orchestration.

Owns the static list of built-in validators and the stage/short-circuit logic.
``validators`` are grouped by responsibility so it is obvious at a glance which
subsystem a given validator belongs to.

The online variant keeps the protocol and semantic stages as its core pipeline.
The quality stage currently hosts deterministic contrast checks; broader design
contract checks remain the responsibility of the ``generateWidgetCard`` service.
"""

from __future__ import annotations

import logging

from .aesthetic_baseline_validator import AestheticBaselineValidator
from .asset_validator import AssetValidator
from .binding_validator import BindingValidator
from .cardspec_validator import CardSpecValidator
from .component_validator import ComponentValidator
from .context import ValidationContext
from .contrast_validator import ContrastValidator
from .cross_validator import CrossValidator
from .diagnostics import Reporter
from .display_unit_validator import DisplayUnitValidator
from .effective_capability_validator import EffectiveCapabilityValidator
from .expression_validator import ExpressionValidator
from .protocol_validator import ProtocolValidator

_LOGGER = logging.getLogger(__name__)

STATIC_VALIDATORS = [
    ProtocolValidator(),
    ComponentValidator(),
    AestheticBaselineValidator(),
    CardSpecValidator(),
    ExpressionValidator(),
    AssetValidator(),
    BindingValidator(),
    DisplayUnitValidator(),
    CrossValidator(),
]

QUALITY_VALIDATORS = [
    ContrastValidator(),
]

EFFECTIVE_VALIDATORS = [
    EffectiveCapabilityValidator(),
]


PIPELINE_BLOCKING_CODES = {
    "DSL_JSON_PARSE_FAILED",
}


def selected_stages(stage: str) -> list[str]:
    if stage == "hard":
        return ["hard"]
    if stage == "semantic":
        return ["hard", "semantic"]
    return ["hard", "semantic", "quality"]


def _has_template_root(context: ValidationContext) -> bool:
    if context.root_id != "root" or context.duplicate_component_ids:
        return False
    root = context.root_component
    template = context.components_by_id.get("template_root")
    if root is None or template is None:
        return False
    children = root.get("children")
    return isinstance(children, list) and "template_root" in children


def run_pipeline(
    context: ValidationContext,
    rules,
    reporter: Reporter,
    stage: str,
    *,
    stop_on_stage_error: bool = False,
) -> None:
    validators = list(STATIC_VALIDATORS) + list(EFFECTIVE_VALIDATORS) + list(QUALITY_VALIDATORS)
    for current_stage in selected_stages(stage):
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        if current_stage == "quality" and _has_template_root(context):
            _LOGGER.info("quality_validation_skipped reason=template_root")
            continue
        for validator in validators:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)
