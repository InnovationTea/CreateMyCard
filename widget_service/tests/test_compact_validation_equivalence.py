"""重放 a42d86a5 冻结基线，仅显式登记后续主线合同的预期变化。"""

import json
from pathlib import Path

import pytest

from services.card_validation import validate_compact_dsl

BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/compact_validation_baseline.json").read_text(
        encoding="utf-8"
    )
)
CASES = BASELINE.get("cases")
assert isinstance(CASES, list)

# bf022115 允许标题图标；SVG 颜色沿用本分支已确认的候选描述策略。
# 冻结快照不重生成，只有这两个旧的“不允许属性”错误迁移到新合同。
TITLE_ICON_ERRORS = {
    "header: SingleLineTitle does not allow icon.": None,
    "header: SingleLineTitle does not allow fillColor.": "SingleLineTitle.fillColor requires icon.",
}

SECONDARY_BODY_ONLY_CASES = {
    1: "body",
    83: "placeholder",
    84: "placeholder",
    110: "title",
    111: "title",
}

# #506 将 compact EventCard 项间距从 8vp 改为 4vp；三项从 112vp 降到 104vp。
# 仅登记这条冻结样本的已确认主线行为变化，不改快照或放宽其它高度错误。
OLD_COMPACT_EVENT_HEIGHT_ERROR = (
    "component body: vertical layout requires at least 112vp within 110vp; "
    "it overflows by 2vp. Regroup facts or choose a layout with enough body space; "
    "preserve required text, actions, font sizes and fixed design heights. "
    "Weight, clipping, flex shrink and distributed alignment cannot eliminate content height. "
    "Occupancy: events=112vp+margin(0vp), gaps=0vp."
)

# #512 将 SecondaryBody 规格改为按实际行布局选择，不再依赖历史 role。
# 冻结样本不重生成，显式登记旧 metadata 12fp 在单行模式下的新错误。
SECONDARY_BODY_FONT_CASES = {
    98: "start_time",
    99: "status",
    101: "battery",
    102: "battery_row",
    103: "score_title",
    108: "condition",
}

SECONDARY_BODY_OLD_HEIGHT_CASES = {76: "condition"}


def _secondary_body_font_error(component_id: str) -> dict:
    message = (
        f"{component_id}: SecondaryBody.fontSize must be the fixed Recipe value 14. "
        "SecondaryBody uses fontSize 14 / lineHeight 19 for a single row and "
        "fontSize 12 / lineHeight 16 for multiple rows. Recompute fontSize after "
        "changing columns, items or maxLines; do not change bindings or delete facts."
    )
    return {
        "exception": "CompactDslValidationError",
        "message": f"Compact DSL validation failed:\n- {message}",
        "errors": [message],
        "cause_type": "CompactDslConversionError",
        "cause_text": message,
    }


def _secondary_body_height_error(component_id: str) -> dict:
    message = (
        f"component {component_id}: vertical layout requires at least 19vp within 18vp; "
        "it overflows by 1vp. Regroup facts or choose a layout with enough body space; "
        "preserve required text, actions, font sizes and fixed design heights. Weight, "
        "clipping, flex shrink and distributed alignment cannot eliminate content height. "
        f"Occupancy: {component_id}_row0=19vp+margin(0vp), gaps=0vp."
    )
    return {
        "exception": "CompactDslValidationError",
        "message": f"Compact DSL validation failed:\n- {message}",
        "errors": [message],
    }


def _expected_after_main_updates(expected: dict, case_index: int) -> dict:
    font_component_id = SECONDARY_BODY_FONT_CASES.get(case_index)
    if font_component_id is not None:
        return _secondary_body_font_error(font_component_id)
    height_component_id = SECONDARY_BODY_OLD_HEIGHT_CASES.get(case_index)
    if height_component_id is not None:
        return _secondary_body_height_error(height_component_id)
    secondary_body_id = SECONDARY_BODY_ONLY_CASES.get(case_index)
    if secondary_body_id is not None:
        message = (
            f"component {secondary_body_id}: SecondaryBody is auxiliary and cannot be the "
            "only information component in its semantic region; pair it with a core "
            "information component. Titles, buttons and other SecondaryBody instances "
            "do not count."
        )
        return {
            "exception": "CompactDslValidationError",
            "message": f"Compact DSL validation failed:\n- {message}",
            "errors": [message],
        }
    errors = expected.get("errors")
    if not isinstance(errors, list) or len(errors) != 1:
        return expected
    if errors == [OLD_COMPACT_EVENT_HEIGHT_ERROR]:
        return {"warnings": []}
    replacement = TITLE_ICON_ERRORS.get(errors[0])
    if errors[0] not in TITLE_ICON_ERRORS:
        return expected
    if replacement is None:
        return {"warnings": []}
    return {
        **expected,
        "errors": [replacement],
        "message": f"Compact DSL validation failed:\n- {replacement}",
    }


@pytest.mark.parametrize(("case_index", "case"), list(enumerate(CASES)))
def test_public_validator_matches_fusion_main(case_index: int, case: dict) -> None:
    inputs = case.get("input")
    expected = case.get("expected")
    assert isinstance(inputs, dict)
    assert isinstance(expected, dict)
    arguments = dict(inputs)
    source = arguments.pop("source")
    observed: dict
    try:
        result = validate_compact_dsl(source, **arguments)
    except Exception as exc:
        observed = {"exception": type(exc).__name__, "message": str(exc)}
        if hasattr(exc, "errors"):
            assert isinstance(exc.errors, tuple)
            observed["errors"] = list(exc.errors)
            assert exc.args == (str(exc),)
        if exc.__cause__ is not None:
            observed["cause_type"] = type(exc.__cause__).__name__
            observed["cause_text"] = str(exc.__cause__)
    else:
        observed = {"warnings": list(result.warnings)}
    assert observed == _expected_after_main_updates(expected, case_index)
