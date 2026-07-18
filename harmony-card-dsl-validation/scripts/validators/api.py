"""Public API for validate_card.

Only responsibility here is to wire input normalization → context building →
pipeline execution. Split into ``inputs.py``, ``effective_loader.py``,
``pipeline.py`` so this file stays small and easy to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import Reporter
from .effective_loader import attach_effective_capabilities
from .inputs import (
    artifact_cardspec_text,
    artifact_dsl,
    cardspec_text,
    effective_from_inputs,
    parse_jsonish,
    unwrap_artifact,
)
from .pipeline import PIPELINE_BLOCKING_CODES, run_pipeline
from .rule_registry import RuleRegistry
from .source_parser import SourceParser, extract_combined


@dataclass
class ValidationOptions:
    stage: str = "all"
    max_errors: int = 50
    stop_on_stage_error: bool = False
    skill_dir: Path | None = None
    capabilities_dir: Path | None = None
    enable_aesthetic: bool = True


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

    artifact_value = unwrap_artifact(parse_jsonish(artifact))
    effective_value = effective_from_inputs(effective_capabilities, artifact_value)

    resolved_dsl = dsl_text or artifact_dsl(artifact_value)
    resolved_cardspec = cardspec_text(cardspec) or artifact_cardspec_text(artifact_value)
    if not resolved_dsl and not resolved_cardspec and isinstance(artifact, str):
        resolved_dsl, resolved_cardspec = extract_combined(artifact)

    context = SourceParser().parse(resolved_dsl, resolved_cardspec, reporter)
    attach_effective_capabilities(
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
            enable_aesthetic=opts.enable_aesthetic,
        )
    return reporter
