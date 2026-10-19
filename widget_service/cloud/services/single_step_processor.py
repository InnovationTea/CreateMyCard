"""只在单步分支调用单步转换器，不进入融合组件/布局处理。"""

import json

from services.card_validation.display_unit_rules import repair_repeated_display_units
from services.generation_pipeline import DslProcessingContext, DslProcessingResult, QualityIssue
from services.single_step_theme import prepare_single_step_theme
from services.widget_edit_protocol.converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    repair_compact_dsl_binding_paths,
)
from services.widget_edit_protocol.resources import PROFILE_DIR


class SingleStepFallbackProcessor:
    def __init__(self, *, post_layout_theme: bool = False):
        self.post_layout_theme = post_layout_theme

    def process(self, source_dsl: str, context: DslProcessingContext) -> DslProcessingResult:
        try:
            source_dsl = repair_compact_dsl_binding_paths(
                source_dsl, task_spec=context.task_spec, card_spec=context.card_spec,
            )
            protocol = json.loads((PROFILE_DIR / "protocol.json").read_text(encoding="utf-8"))
            protocol["appVersion"] = context.task_spec.get("appVersion")
            standard = convert_compact_dsl_to_a2ui(
                source_dsl, size=context.size, protocol_profile=protocol,
            )
            standard = repair_repeated_display_units(
                standard, context.card_spec, context.data_capabilities,
            )
        except CompactDslConversionError as exc:
            issue = QualityIssue(stage="conversion", code="SINGLE_STEP_COMPACT_CONVERSION_FAILED",
                                 message=str(exc))
            return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))
        if self.post_layout_theme:
            try:
                standard = prepare_single_step_theme(
                    standard, source_dsl, {**context.task_spec, "size": context.size},
                )
            except ValueError as exc:
                issue = QualityIssue(stage="conversion", code="SINGLE_STEP_THEME_HANDOFF_FAILED",
                                     message=str(exc))
                return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))
        return DslProcessingResult(source_dsl=source_dsl, standard_dsl=standard)
