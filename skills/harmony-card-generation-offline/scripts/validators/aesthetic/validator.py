"""DSL-only deterministic aesthetic quality validator for HarmonyOS A2UI Form cards.

Wraps the standalone aesthetic engine (see ``engine.py``, v0.2.1) to fit the
BaseValidator pipeline.  All aesthetic checks — contrast, palette, typography,
layout density, style consistency, interaction affordance — are delegated to
that engine.
"""

from __future__ import annotations

from typing import Any

from .engine import Thresholds, analyze
from ..base import BaseValidator


class QualityValidator(BaseValidator):
    """Third-stage aesthetic quality validation.

    Receives the already-parsed ValidationContext and feeds its raw DSL text
    to the deterministic aesthetic analyser.  Diagnostics are forwarded into
    the pipeline reporter and a 0–100 quality score is computed.
    """

    stage = "quality"
    name = "quality"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        if not context.dsl_messages:
            return

        # ------------------------------------------------------------------
        # Build thresholds from rules config (with sensible defaults)
        # ------------------------------------------------------------------
        layout_rules = getattr(rules, "layout", {}) or {}
        thresholds = Thresholds(
            normal_text_min=float(layout_rules.get("contrastNormalTextMin", 4.5)),
            large_text_min=float(layout_rules.get("contrastLargeTextMin", 3.0)),
            critical_min=float(layout_rules.get("contrastCriticalMin", 3.0)),
            large_font_size=float(layout_rules.get("contrastLargeFontSize", 18.0)),
            large_bold_font_size=float(layout_rules.get("contrastLargeBoldFontSize", 14.0)),
            large_bold_font_weight=float(layout_rules.get("contrastLargeBoldFontWeight", 700.0)),
            max_chromatic_families=int(layout_rules.get("maxChromaticFamilies", 2)),
            max_gradient_surfaces=int(layout_rules.get("maxGradientSurfaces", 1)),
            max_gradient_stops=int(layout_rules.get("maxGradientStops", 3)),
            max_translucent_surface_layers=int(layout_rules.get("maxTranslucentSurfaceLayers", 2)),
            max_font_size_levels=int(layout_rules.get("maxFontSizeLevels", 3)),
            max_radius_values=int(layout_rules.get("maxRadiusValues", 3)),
            max_shadowed_components=int(layout_rules.get("maxShadowedComponents", 2)),
            max_border_width_values=int(layout_rules.get("maxBorderWidthValues", 2)),
            max_nested_surfaces=int(layout_rules.get("maxNestedSurfaces", 2)),
        )

        # ------------------------------------------------------------------
        # Run the aesthetic engine
        # ------------------------------------------------------------------
        report = analyze(context.dsl_text, thresholds)

        # ------------------------------------------------------------------
        # Forward every diagnostic to the pipeline reporter
        # ------------------------------------------------------------------
        for diag in report.get("diagnostics", []):
            reporter.add(
                diag.get("severity", "warning"),
                diag.get("code", "AESTHETIC_UNKNOWN"),
                "quality",
                "genui",
                line=diag.get("line"),
                json_pointer=diag.get("jsonPointer", ""),
                actual=diag.get("actual"),
                expected=diag.get("expected"),
                message=diag.get("message", ""),
                fix_hint=diag.get("fixHint", ""),
            )

        # ------------------------------------------------------------------
        # Compute 0–100 quality score
        # ------------------------------------------------------------------
        summary = report.get("summary", {})
        error_count = summary.get("errorCount", 0)
        warning_count = summary.get("warningCount", 0)
        needs_review = summary.get("needsReviewCount", 0)
        score = max(0, 100 - error_count * 10 - warning_count * 3 - needs_review * 2)
        context.quality_score = score
        reporter.set_quality(score)
