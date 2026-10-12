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
    "header: SingleLineTitle does not allow icon.": (
        "component header: tintable SVG resources/heart.svg must set fillColor explicitly; "
        "omitting it renders the asset's default black."
    ),
    "header: SingleLineTitle does not allow fillColor.": "SingleLineTitle.fillColor requires icon.",
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


def _expected_after_main_updates(expected: dict) -> dict:
    errors = expected.get("errors")
    if not isinstance(errors, list) or len(errors) != 1:
        return expected
    if errors == [OLD_COMPACT_EVENT_HEIGHT_ERROR]:
        return {"warnings": []}
    replacement = TITLE_ICON_ERRORS.get(errors[0])
    if replacement is None:
        return expected
    return {
        **expected,
        "errors": [replacement],
        "message": f"Compact DSL validation failed:\n- {replacement}",
    }


@pytest.mark.parametrize("case", CASES)
def test_public_validator_matches_fusion_main(case: dict) -> None:
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
    assert observed == _expected_after_main_updates(expected)
