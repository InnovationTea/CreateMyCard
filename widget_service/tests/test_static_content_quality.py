"""静态展示的结构选型、主题隔离及不依赖业务词的回归。"""

import copy
import json

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.post_layout_theme import apply_theme, foreground_signature
from services.post_layout_theme_registry import fallback_theme
from services.static_content_context import standard_components
from services.static_content_presentation import (
    static_presentation_candidates,
    trial_static_presentation,
)
from services.theme_selection_policy import default_palette_family
from services.theme_style_roles import layout_phase


def _fact(text, role=None, **extras):
    value = {"requirement": text, "text": text, "sourceTexts": [text], "priority": "must"}
    if role:
        value["displayRole"] = role
    value.update(extras)
    return value


def _plan():
    return {
        "info_required": [
            _fact("甲对象", "title"), _fact("须预约", "body"), _fact("周六", "trailing"),
            _fact("乙对象", "title"), _fact("无需预约", "body"), _fact("周日", "trailing"),
        ],
        "contentGroups": [
            {"id": "a", "kind": "object", "factIndexes": [0, 1, 2]},
            {"id": "b", "kind": "object", "factIndexes": [3, 4, 5]},
        ],
        "presentationStyle": "records",
        "paletteFamily": "auto",
    }


def _accept(plan, size="2x4"):
    texts = [fact.get("text", "") for fact in plan.get("info_required", [])]
    task = {"userQuery": "；".join(texts), "size": size}
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    return parse_compact_plan_call(raw, task).plan


@pytest.fixture
def static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


@pytest.mark.usefixtures("static_scope")
def test_roles_create_readable_records_without_synthetic_labels():
    accepted = _accept(_plan())
    dsl = accepted.get("staticPresentation")
    assert isinstance(dsl, str)
    rows = [json.loads(line) for line in dsl.splitlines()]
    body = next(row for row in rows if row[0] == "body")
    assert body[1] == "RecordList"
    assert body[2].get("items") == [
        {"title": "甲对象", "description": "须预约", "trailing": "周六"},
        {"title": "乙对象", "description": "无需预约", "trailing": "周日"},
    ]
    assert '"信息"' not in dsl


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("query", ["横向并排", "旅行演出保险", "arbitrary topic", ""])
def test_query_words_do_not_choose_layout_or_rewrite_plan(query):
    value = _plan()
    before = copy.deepcopy(value)
    trial = trial_static_presentation(value, query, "2x4")
    assert trial.source == trial_static_presentation(value, "另一个请求", "2x4").source
    assert value == before


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("role", [None, 0, {}, "unknown"])
def test_invalid_role_is_a_plan_error(role):
    value = _plan()
    facts = value.get("info_required")
    assert facts
    facts[0]["displayRole"] = role
    with pytest.raises(CompactPlanValidationError, match="displayRole"):
        _accept(value)


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("key", ["presentationStyle", "paletteFamily"])
def test_static_preferences_validate_enumerations(key):
    value = _plan()
    value[key] = ["unknown"]
    with pytest.raises(CompactPlanValidationError, match=key):
        _accept(value)


def test_dynamic_plan_does_not_accept_static_roles_or_preferences():
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError):
            _accept(_plan())


@pytest.mark.usefixtures("static_scope")
def test_comparison_shape_comes_from_plan_and_preserves_object_names():
    value = _plan()
    value["presentationStyle"] = "comparison"
    for fact in value.get("info_required", []):
        if fact.get("displayRole") == "body":
            fact["displayRole"] = "value"
    accepted = _accept(value)
    dsl = accepted.get("staticPresentation")
    assert dsl and "ComparisonGroup" in dsl
    assert "甲对象" in dsl and "乙对象" in dsl
    candidates = static_presentation_candidates(accepted, "2x4")
    assert all("ComparisonGroup" in source for source in candidates)
    with pytest.raises(CompactPlanValidationError, match="2x4"):
        _accept(value, "2x2")


@pytest.mark.usefixtures("static_scope")
def test_unlabelled_attributes_keep_every_object_without_placeholder_cost():
    value = _plan()
    value["presentationStyle"] = "attributes"
    for fact in value.get("info_required", []):
        fact.pop("displayRole", None)
    accepted = _accept(value)
    dsl = accepted.get("staticPresentation")
    assert dsl and "ContentBlock" in dsl and '"label"' not in dsl
    for fact in value.get("info_required", []):
        assert fact.get("text") in dsl


@pytest.mark.usefixtures("static_scope")
def test_long_optional_note_can_be_omitted_without_mutating_accepted_core():
    value = _plan()
    facts = value.get("info_required")
    groups = value.get("contentGroups")
    assert facts and groups
    facts.append(_fact("来源说明" * 100, priority="should"))
    groups.append({"id": "note", "kind": "shared", "factIndexes": [6]})
    before = copy.deepcopy(value)
    accepted = _accept(value)
    dsl = accepted.get("staticPresentation")
    assert dsl and "来源说明" not in dsl
    feedback = accepted.get("staticPresentationFeedback")
    assert feedback and "省略" in feedback[0]
    assert accepted.get("info_required") == value.get("info_required")
    assert value == before
    from services.compact_plan import compact_plan_omitted_facts

    omitted = compact_plan_omitted_facts(dsl, accepted, {}, ())
    assert len(omitted) == 1
    assert omitted[0].get("omissionReason") == "optional_omission"


@pytest.mark.usefixtures("static_scope")
def test_attribute_value_columns_share_width_and_align_end():
    rows = [
        ["root", "Layout", {"layout": "W-static-content"}, ["body"]],
        ["body", "ContentBlock", {"attributes": [
            {"label": "甲", "value": "20元", "valueRole": "value"},
            {"label": "较长标签", "value": "30元", "valueRole": "value"},
        ]}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    nodes = standard_components(convert_compact_dsl_to_a2ui(source, size="2x4"))
    first = nodes.get("body__static_attr0_value", {}).get("styles", {})
    second = nodes.get("body__static_attr1_value", {}).get("styles", {})
    assert first.get("width") == second.get("width")
    assert first.get("textAlign") == second.get("textAlign") == "end"


def test_static_palette_is_diverse_stable_and_dynamic_default_stays_blue():
    families = set()
    for index in range(30):
        task = {"userQuery": f"普通内容{index}", "dataModelSchema": {"data": {}}}
        with content_policy_scope(STATIC_CONTENT_POLICY):
            family = default_palette_family(task)
            families.add(family)
            assert family == default_palette_family({**task, "uid": "another", "size": "2x4"})
        with content_policy_scope(EXISTING_CONTENT_POLICY):
            assert default_palette_family(task) == "blue"
    assert families == {"blue", "purple", "warm"}


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_static_panels_use_light_theme_surface_and_freeze_geometry(family):
    value = _plan()
    value["presentationStyle"] = "comparison"
    for fact in value.get("info_required", []):
        if fact.get("displayRole") == "body":
            fact["displayRole"] = "value"
    task = {"userQuery": "静态内容", "size": "2x4", "staticPaletteFamily": family}
    assert default_palette_family(task) == family
    dsl = _accept(value).get("staticPresentation")
    assert isinstance(dsl, str)
    with layout_phase(True):
        standard = convert_compact_dsl_to_a2ui(dsl, size="2x4")
    theme = fallback_theme(family)
    themed = apply_theme(standard, theme, task, {})
    assert foreground_signature(standard) == foreground_signature(themed)
    panel = theme.get("content", {}).get("panelBySize", {}).get("2x4")
    nodes = standard_components(themed)
    for index in range(2):
        node = nodes.get(f"body__static_item{index}")
        assert node is not None
        assert node.get("styles", {}).get("backgroundColor") == panel


@pytest.mark.asyncio
@pytest.mark.parametrize("refinement", ["valid", "invalid", "unfit"])
async def test_plan_refines_within_existing_budget_and_keeps_last_valid_plan(
    monkeypatch, refinement,
):
    from types import SimpleNamespace

    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    value = {
        "info_required": [_fact("带证件", "body")],
        "contentGroups": [{"id": "a", "kind": "object", "factIndexes": [0], "identity": None}],
        "paletteFamily": "warm",
    }
    calls = []
    theme_tasks = []
    saved = []

    async def generate(_client, messages, profile=None, **_kwargs):
        output_format = (profile or {}).get("format")
        calls.append(output_format)
        if output_format == "raw-json":
            if calls.count("raw-json") == 2:
                assert "capacityReference" in messages[-1].get("content", "")
                if refinement == "invalid":
                    return '{"invalid": true}'
            return json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)
        return '\n'.join([
            '["root","Layout",{"layout":"S-static-content"},["body"]]',
            '["body","ContentBlock",{"body":"带证件"}]',
            '["/state/ready",true]',
        ])

    async def theme(artifact, task, *_args, **_kwargs):
        theme_tasks.append(task)
        return artifact

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(artifactUrl="https://artifact.test/quality", artifactDigest="local")

    trial_calls = []
    continuation_plans = []
    from services.prompt_builder import PromptBuilder

    original_continuation = PromptBuilder.build_compact_dsl_continuation

    def trial(*_args):
        trial_calls.append(True)
        candidate = None
        if refinement == "unfit" and len(trial_calls) == 1:
            candidate = "此前可行候选"
        return SimpleNamespace(source=candidate, errors=("有限候选未通过",))

    def continuation(conversation, task, accepted_plan, **kwargs):
        continuation_plans.append(accepted_plan)
        return original_continuation(conversation, task, accepted_plan, **kwargs)

    monkeypatch.setattr(PromptBuilder, "build_compact_dsl_continuation", continuation)
    monkeypatch.setattr("services.static_content_presentation.trial_static_presentation", trial)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    monkeypatch.setattr("services.post_layout_theme.theme_artifact", theme)
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    request = GenerateWidgetCardRequest(
        uid="quality-refinement", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="制作带证件的提醒卡", size="2x2", title="出发前", description="出发前提醒",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status.value == "success"
    assert calls == ["raw-json", "raw-json", "compact-dsl"]
    assert len(saved) == 1
    if refinement == "unfit":
        assert continuation_plans[0].get("staticPresentation") == "此前可行候选"
    assert theme_tasks[0].get("staticPaletteFamily") == "warm"
    assert "staticPaletteFamily" not in saved[0].taskSpec


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("alias,canonical", [
    ("description", "body"), ("primaryText", "value"),
    ("secondaryText", "title"), ("details", "detail"),
])
def test_component_field_roles_normalize_without_query_heuristics(alias, canonical):
    value = _plan()
    facts = value.get("info_required")
    assert facts
    facts[0]["displayRole"] = alias
    accepted = _accept(value)
    actual = accepted.get("info_required")
    assert actual
    assert actual[0].get("displayRole") == canonical
