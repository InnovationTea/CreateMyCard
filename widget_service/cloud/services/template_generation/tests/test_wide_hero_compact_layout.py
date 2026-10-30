"""Hero + 按钮 / Full 与单个 Compact 的独立布局合同。"""

import pytest

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.advanced.models import AdvancedScopeBrief
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    _layout_output_option,
    _second_layer_layout_selection,
)
from services.template_generation.engine.cardplan.compiler import (
    _validate_provider_template_layout_action_requirements,
)
from services.template_generation.engine.cardplan.models import SourceSpan
from services.template_generation.engine.cardplan.parser import ParsedCall
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.wide_template_planner import _WIDE_LAYOUTS
from services.template_generation.engine.tersel_converter import TerselConversionError

_HERO = "HeartRateOverviewHero@1"
_FULL = "HeartRateOverviewFull@1"
_COMPACT = "BluetoothDeviceOverviewEarphoneCaseCompact@1"


def _template(template_id: str) -> ParsedCall:
    return ParsedCall("template", template_id, ({},), (), SourceSpan(start=0, end=1))


@pytest.mark.parametrize(
    ("layout", "primary", "actions", "valid"),
    [
        ("WideHeroCompactLayout", _HERO, ("PillAction@1",), True),
        ("WideHeroCompactLayout", _HERO, (), False),
        ("WideHeroCompactLayout", _HERO, ("CompactAction@1",), False),
        ("WideHeroCompactLayout", _HERO, ("PillAction@1",) * 2, False),
        ("WideHeroCompactLayout", _FULL, ("PillAction@1",), False),
        ("WideFullCompactLayout", _FULL, (), True),
        ("WideFullCompactLayout", _HERO, (), False),
        ("WideFullCompactLayout", _FULL, ("PillAction@1",), False),
    ],
)
def test_compiler_rejects_missing_button_and_wrong_roles(layout, primary, actions, valid):
    contents = (_template(primary), _template(_COMPACT))
    action_calls = tuple(_template(name) for name in actions)
    if valid:
        _validate_provider_template_layout_action_requirements(
            layout,
            contents,
            action_calls,
            "2x4",
        )
    else:
        with pytest.raises(TerselConversionError, match="slot combination is invalid"):
            _validate_provider_template_layout_action_requirements(
                layout,
                contents,
                action_calls,
                "2x4",
            )


@pytest.mark.parametrize(
    ("primary", "action_count", "layout", "action_templates"),
    [
        (_HERO, 1, "WideHeroCompactLayout", ("PillAction@1",)),
        (_FULL, 0, "WideFullCompactLayout", ()),
    ],
)
def test_second_layer_projects_distinct_layout_and_button(
    primary, action_count, layout, action_templates
):
    actions = (
        [
            EventAction(
                id="event.open.health.sport",
                call="clickToDeeplink",
                args={"uri": "health:sport"},
            )
        ]
        if action_count
        else []
    )
    task = TaskSpec(
        userQuery="心率与耳机电量", size="2x4", dataModelSchema={}, eventCandidates=actions
    )
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("HeartRateOverview", "BluetoothDeviceOverview"),
    )
    groups = ((primary,), (_COMPACT,))
    selection = _second_layer_layout_selection(
        scope,
        task,
        get_cardplan_registry(),
        required_template_groups=groups,
    )
    assert selection.layout_ids == (layout,)
    assert selection.action_template_ids == action_templates
    selected_actions = ({"actionId": "event.open.health.sport", "label": "打开锻炼"},)
    option = _layout_output_option(
        layout + "@1",
        groups,
        selected_actions if action_count else (),
        action_templates,
    )
    assert option.get("businessTemplateIdsByPosition") == groups
    children = option.get("actionChildren")
    assert isinstance(children, list)
    assert len(children) == action_count
    if action_count:
        assert children[0].get("templateId") == "PillAction@1"
        assert children[0].get("position") == 2


def test_second_layer_does_not_invent_button_for_no_action_hero_request():
    task = TaskSpec(userQuery="心率和耳机电量，不要按钮", size="2x4", dataModelSchema={})
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("HeartRateOverview", "BluetoothDeviceOverview"),
    )
    with pytest.raises(ValueError, match="Hero .* Compact requires one PillAction"):
        _second_layer_layout_selection(
            scope,
            task,
            get_cardplan_registry(),
            required_template_groups=((_HERO,), (_COMPACT,)),
        )


@pytest.mark.parametrize(
    ("layout", "roles", "actions", "owners"),
    [
        ("WideHeroCompactLayout", ("Hero", "Compact"), ("PillAction",), (0,)),
        ("WideFullCompactLayout", ("Full", "Compact"), (), ()),
    ],
)
def test_planner_and_registry_require_the_independent_approved_contract(
    layout, roles, actions, owners
):
    options = [option for option in _WIDE_LAYOUTS if option.layout_id == layout]
    assert len(options) == 1
    option = options[0]
    assert option.roles == roles
    assert option.action_templates == actions
    assert option.action_owners == owners
    assert not option.allows_embedded_action
    definition = get_cardplan_registry().require_ux_layout_component(layout)
    assert definition.supported_card_sizes == ("2x4",)
    assert definition.min_action_children_by_size.get("2x4") == len(actions)
    assert definition.max_action_children_by_size.get("2x4") == len(actions)


@pytest.mark.parametrize(
    ("layout", "action_id", "valid"),
    [
        ("WideHeroCompactLayout", "event.open.health.sport", True),
        ("WideHeroCompactLayout", None, False),
        ("WideHeroCompactLayout", "event.open.settings.bluetooth", False),
        ("WideFullCompactLayout", None, True),
        ("WideFullCompactLayout", "event.open.health.sport", False),
    ],
)
def test_planner_preserves_action_count_and_business_owner(layout, action_id, valid):
    from models.generation import CandidateDataBinding
    from services.template_generation.engine.cardplan.template_plan_planner import (
        plan_template_candidates,
    )
    from services.template_generation.engine.cardplan.template_retrieval import (
        TemplateRetrievalMiss,
        TemplateSearchIntent,
        search_template_variants,
    )
    from services.template_generation.tests.test_template_retrieval import _field

    actions = []
    if action_id:
        actions.append(EventAction(id=action_id, call="clickToDeeplink", args={"uri": "test:open"}))
    task = TaskSpec(
        userQuery="运动平均心率与耳机仓电量",
        size="2x4",
        eventCandidates=actions,
        dataModelSchema={
            "data": {
                "healthSport": {"exerciseHeartRateAvg": _field(135, "integer")},
                "earphone": {
                    "batteryLevel": _field(80, "integer"),
                    "chargingStatusDesc": _field("未充电"),
                },
            }
        },
    )
    fields = {
        "GetHealthAndSportSummary": ("/exerciseHeartRateAvg",),
        "GetEarphoneInfo": ("/batteryLevel", "/chargingStatusDesc"),
    }
    bindings = (
        CandidateDataBinding(
            capabilityId="GetHealthAndSportSummary",
            writeResultTo="/data/healthSport",
            candidateOutputFields=["/exerciseHeartRateAvg"],
        ),
        CandidateDataBinding(
            capabilityId="GetEarphoneInfo",
            writeResultTo="/data/earphone",
            candidateOutputFields=["/batteryLevel", "/chargingStatusDesc"],
        ),
    )
    card = {
        "title": "心率与耳机",
        "suggestSize": "2x4",
        "dataBindings": [
            {"capabilityId": binding.capabilityId, "writeResultTo": binding.writeResultTo}
            for binding in bindings
        ],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability=fields, action=(action_id,) if action_id else ()
    )
    registry = get_cardplan_registry()
    found = search_template_variants(intent, task, registry, bindings, card)
    if valid:
        plans = plan_template_candidates(
            intent, found, task, registry, allowed_layout_ids=(layout + "@1",)
        )
        assert plans
        for plan in plans:
            assert plan.layout_template_id == layout + "@1"
            assert len(plan.action_assignments) == len(actions)
            if actions:
                assignment = plan.action_assignments[0]
                assert assignment.action_template_id == "PillAction@1"
                assert assignment.business_position == 0
                assert assignment.action_id == action_id
    else:
        with pytest.raises(TemplateRetrievalMiss, match="supported atomic plan"):
            plan_template_candidates(
                intent, found, task, registry, allowed_layout_ids=(layout + "@1",)
            )
