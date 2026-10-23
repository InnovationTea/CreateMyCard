"""三条日历兜底均须保留受信骨架限制，拒绝时不进入第二层模型。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced.scope_planner import TemplateRouteNotApplicable
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs
from services.template_generation.tests.test_calendar_list_no_action_fallback import (
    _case as _list_case,
)
from services.template_generation.tests.test_calendar_no_action_fallback import (
    _case as _single_case,
)
from services.template_generation.tests.test_calendar_richeng3_no_action_fallback import _mixed


@dataclass(frozen=True)
class _LayoutCase:
    inputs: CalendarInputs
    templates: tuple[str, ...]
    layout: str
    forbidden_layout: str
    fallback_name: str


@pytest.fixture(params=["single", "list", "mixed"])
def layout_case(request: pytest.FixtureRequest) -> _LayoutCase:
    if request.param == "single":
        result = _LayoutCase(
            inputs=_single_case(
                "2x4", ("/events/0/timeZone", "/events/0/dtStart", "/events/0/eventLocation"),
            ),
            templates=("ScheduleOverviewTimezoneWideFull@1",),
            layout="WideFullOnlyLayout@1",
            forbidden_layout="WideTwoFullLayout@1",
            fallback_name="plan_calendar_no_action_fallback",
        )
    elif request.param == "list":
        result = _LayoutCase(
            inputs=_list_case(),
            templates=("ScheduleOverviewEventCountThreeNotesWideFull@1",),
            layout="WideFullOnlyLayout@1",
            forbidden_layout="WideTwoFullLayout@1",
            fallback_name="plan_calendar_list_no_action_fallback",
        )
    else:
        assert request.param == "mixed"
        result = _LayoutCase(
            inputs=_mixed(),
            templates=("ScheduleOverviewDateTitleFull@1", "WeatherOverviewFull@1"),
            layout="WideTwoFullLayout@1",
            forbidden_layout="WideFullOnlyLayout@1",
            fallback_name="plan_calendar_weather_no_action_fallback",
        )
    return result


@pytest.mark.parametrize("restriction", ["default", "allowed", "forbidden"])
@pytest.mark.asyncio
async def test_calendar_fallback_preserves_layout_constraint_before_second_layer(
    monkeypatch: pytest.MonkeyPatch, layout_case: _LayoutCase, restriction: str,
) -> None:
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    registry = CardPlanRegistry()
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)
    original_fallback = getattr(pipeline, layout_case.fallback_name)
    fallback_calls: list[dict[str, Any]] = []

    def record_fallback(*args: Any, **kwargs: Any) -> Any:
        fallback_calls.append(kwargs)
        return original_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, layout_case.fallback_name, record_fallback)
    inputs = layout_case.inputs
    original = deepcopy(inputs)
    model_calls: list[str] = []

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            model_calls.append("intent")
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            model_calls.append("body")
            children = ",".join(f'Template("{target}",{{}})' for target in layout_case.templates)
            return f'Template("{layout_case.layout}",{{}},{children});'

    layout_ids: tuple[str, ...] = ()
    if restriction == "allowed":
        layout_ids = (layout_case.layout,)
    elif restriction == "forbidden":
        layout_ids = (layout_case.forbidden_layout,)
    arguments = (inputs.task, inputs.card, inputs.bindings, Model())
    if restriction == "forbidden":
        with pytest.raises(TemplateRouteNotApplicable):
            await pipeline.generate_template_a2ui(
                *arguments, trusted_template_layout_ids=layout_ids,
            )
        assert model_calls == ["intent"]
    else:
        output = await pipeline.generate_template_a2ui(
            *arguments, trusted_template_layout_ids=layout_ids,
        )
        assert layout_case.layout in output.template_ids
        assert set(layout_case.templates).issubset(output.template_ids)
        assert model_calls == ["intent", "body"]
    assert len(fallback_calls) == 1
    assert fallback_calls[0].get("trusted_template_layout_ids") == layout_ids
    assert inputs == original
