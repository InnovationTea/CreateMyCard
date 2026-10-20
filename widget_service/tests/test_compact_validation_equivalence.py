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

SECONDARY_BODY_OLD_HEIGHT_CASES = {
    76: "condition",
    108: "condition",
}

SECONDARY_BODY_WIDTH_CASES = {77, 109}
RETIRED_WIND_LABEL_CASE = 24


def _secondary_body_width_error() -> dict:
    message = (
        "component current_item1: text width overflow; complete label '电压' plus "
        "compound value '4V' requires about 39vp of pressure width within 38.4vp at "
        "the original body font. Keep the full label and value; use legal two-line "
        "body text at the same font and budget its height, or regroup. Weight, "
        "clipping and dropping units do not close this text budget."
    )
    return {
        "exception": "CompactDslValidationError",
        "message": f"Compact DSL validation failed:\n- {message}",
        "errors": [message],
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
    if case_index == RETIRED_WIND_LABEL_CASE:
        remaining_error = expected.get("errors", [])[0]
        return {
            "exception": "CompactDslValidationError",
            "message": f"Compact DSL validation failed:\n- {remaining_error}",
            "errors": [remaining_error],
        }
    if case_index in SECONDARY_BODY_WIDTH_CASES:
        return _secondary_body_width_error()
    height_component_id = SECONDARY_BODY_OLD_HEIGHT_CASES.get(case_index)
    if height_component_id is not None:
        return _secondary_body_height_error(height_component_id)
    secondary_body_id = SECONDARY_BODY_ONLY_CASES.get(case_index)
    if secondary_body_id is not None:
        message = (
            f"component {secondary_body_id}: SecondaryBody is auxiliary and cannot be the "
            "only information component in the card; pair it with a core information "
            "component somewhere in the card. Titles, buttons and other SecondaryBody "
            "instances do not count."
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
