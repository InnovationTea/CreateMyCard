"""Q053 检索、布局与收藏歌单动作回归。"""

import json
from pathlib import Path

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteSelection,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    _preview_theme,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import TemplateRetrievalQuery
from services.template_generation.engine.cardplan.wide_full_planner import plan_embedded_wide_full
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.helpers.generate_q053_preview import TEMPLATE_ID, generate


@pytest.fixture(scope="module")
def messages(tmp_path_factory):
    output = tmp_path_factory.mktemp("q053") / "preview.json"
    generate(Path(__file__).parent / "fixtures/q053.json", output)
    return json.loads(output.read_text(encoding="utf-8"))


def test_q053_compiles_with_two_rings_and_exact_favorite_action(messages):
    update = messages[1].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    rings = [node for node in nodes if node.get("component") == "Progress"]
    assert len(rings) == 2
    for ring in rings:
        styles = ring.get("styles", {})
        assert styles.get("width") == styles.get("height") == 44
        assert styles.get("strokeWidth") == 6
    text = json.dumps(messages, ensure_ascii=False)
    assert "favoriteSong" in text
    assert "收藏歌单" in text
    assert "示例数据" not in text
    assert "sendToAssistant" not in text


def test_q053_music_left_and_earbuds_right(messages):
    update = messages[1].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    music = next(node for node in nodes if node.get("styles", {}).get("padding") == 8)
    button = next(node for node in nodes if node.get("styles", {}).get("height") == 36)
    assert button.get("id") in music.get("children", [])
    panels = [
        node
        for node in nodes
        if node.get("component") == "Row" and node.get("styles", {}).get("layoutWeight") == 1
    ]
    assert len(panels) == 2
    row = next(node for node in nodes if music.get("id") in node.get("children", []))
    assert row.get("children", [])[0] == music.get("id")
    assert row.get("itemMargin") == 12
    assert music.get("styles", {}).get("height") == "matchParent"
    assert row.get("styles", {}).get("height") == "matchParent"


@pytest.mark.parametrize("scenario", ["2x2", "no_action", "wrong_action", "legacy", "extra_field"])
def test_non_opted_inputs_preserve_legacy_route(scenario):
    registry = CardPlanRegistry()
    definition = registry.require_template(TEMPLATE_ID)
    theme = _preview_theme(definition, registry)
    template_id = "BluetoothDeviceOverviewEarbudsFull@1" if scenario == "legacy" else TEMPLATE_ID
    event_id = (
        "event.open.clock.alarm" if scenario == "wrong_action" else "event.open.music.favorite"
    )
    fields = definition.primary_data + definition.secondary_data
    if scenario == "extra_field":
        fields += ("/earphoneName",)
    query = TemplateRetrievalQuery(
        themeId=theme.theme_profile_id,
        requiredOutputFieldsByCapability={"GetEarphoneInfo": fields},
        action=() if scenario == "no_action" else (event_id,),
    )
    selection = TemplateRouteSelection(
        scope=AdvancedScopeBrief(
            themeId=theme.theme_profile_id,
            advancedComponentIds=("BluetoothDeviceOverview",),
        ),
        componentCandidates=(
            TemplateComponentCandidate(
                componentId="BluetoothDeviceOverview",
                availableTemplateIds=(template_id,),
            ),
        ),
        actionIds=query.action_ids,
    )
    task = TaskSpec(
        userQuery="耳机音乐",
        size="2x2" if scenario == "2x2" else "2x4",
        dataModelSchema={},
        eventCandidates=[EventAction(id=event_id, call="clickToDeeplink", args={})],
    )
    before = selection.model_dump()
    assert plan_embedded_wide_full(query, selection, task, registry) == ()
    assert selection.model_dump() == before


@pytest.mark.asyncio
async def test_q053_production_pipeline_preserves_internal_action():
    payload = json.loads((Path(__file__).parent / "fixtures/q053.json").read_text(encoding="utf-8"))
    content = payload.get("content", payload)
    registry = CardPlanRegistry()
    definition = registry.require_template(TEMPLATE_ID)
    event = content.get("candidateEventCandidates", [])[0]
    action = event.get("action")
    assert isinstance(action, dict)
    task = TaskSpec(
        userQuery=content.get("userQuery"),
        size="2x4",
        dataModelSchema=_build_data_schema(definition),
        eventCandidates=[EventAction(id="event.open.music.favorite", **action)],
    )
    bindings = tuple(
        CandidateDataBinding.model_validate(item)
        for item in content.get("candidateDataBindings", [])
    )

    class Model:
        async def generate_json(self, _prompt, *, phase):
            assert phase == "template-retrieval-query"
            return {
                "requiredOutputFieldsByCapability": {
                    "GetEarphoneInfo": definition.primary_data + definition.secondary_data,
                },
                "action": ["event.open.music.favorite"],
            }

        async def generate(self, prompt, _profile, **_kwargs):
            assert "WideFullOnlyLayout@1" in str(prompt)
            assert "business-template" in str(prompt)
            return (
                'Template("WideFullOnlyLayout@1",{},'
                f'Template("{TEMPLATE_ID}",{{"actionId":"event.open.music.favorite"}}));'
            )

    result = await generate_template_a2ui(
        task,
        {"suggestSize": "2x4", "dataBindings": [item.model_dump() for item in bindings]},
        bindings,
        Model(),
    )
    assert TEMPLATE_ID in result.template_ids
    assert "WideFullOnlyLayout@1" in result.template_ids
    assert "PillAction@1" not in result.template_ids
