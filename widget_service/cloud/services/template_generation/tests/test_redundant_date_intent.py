"""移除被天气日期覆盖的空业务，同时保留独立概览和明确选择。"""

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    normalize_redundant_date_intent,
)


def _binding(fields: tuple[str, ...]) -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="GetCurrentTime", writeResultTo="/data/time",
        candidateOutputFields=list(fields),
    )


def test_redundant_date_is_removed_without_mutating_original() -> None:
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={
        "ViewWeather": ("/daily/1/date", "/daily/1/weekday", "/daily/1/condition"),
        "GetCurrentTime": (),
    })
    result = normalize_redundant_date_intent(
        intent, (_binding(("/currentDate", "/dayOfWeek")),),
    )
    assert result.required_output_fields_by_capability == {
        "ViewWeather": ("/daily/1/date", "/daily/1/weekday", "/daily/1/condition"),
    }
    assert "GetCurrentTime" in intent.required_output_fields_by_capability


@pytest.mark.parametrize(
    ("weather", "clock", "candidates", "actions"),
    [
        ((), (), ("/currentDate",), ()),
        (("/current/condition",), (), ("/currentDate",), ()),
        (("/daily/1/weekday",), (), ("/currentDate",), ()),
        (("/daily/1/date",), ("/currentDate",), ("/currentDate",), ()),
        (("/daily/1/date",), (), ("/currentTime",), ()),
        (("/daily/1/date",), (), (), ()),
        (("/daily/1/date",), (), ("/currentDate",), ("event.openClock",)),
    ],
)
def test_independent_overviews_fields_and_actions_are_preserved(
    weather: tuple[str, ...], clock: tuple[str, ...],
    candidates: tuple[str, ...], actions: tuple[str, ...],
) -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"ViewWeather": weather, "GetCurrentTime": clock},
        action=actions,
    )
    assert normalize_redundant_date_intent(intent, (_binding(candidates),)) is intent


def test_only_empty_clock_business_is_preserved() -> None:
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetCurrentTime": ()})
    assert normalize_redundant_date_intent(intent, (_binding(("/currentDate",)),)) is intent
