"""图标叠放白名单、候选过滤及验收全集回归。"""

import hashlib
import json

import pytest
from PIL import Image

from services.template_generation.engine.advanced.ux_mixed_prompt import (
    _allows_single_action_template,
)
from services.template_generation.engine.cardplan.compiler import _validate_ux_layout_root
from services.template_generation.engine.cardplan.full_icon_action_policy import (
    ACTION_ID,
    LAYOUT_ID,
    load_full_icon_action_allowlist,
    template_digest,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, SourceSpan
from services.template_generation.engine.cardplan.parser import ParsedCall
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    _single_business_drafts,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchCandidate,
    TemplateSearchIntent,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.tests.test_template_generation import _battery_task
from services.template_generation.tools.generate_full_icon_action_gallery import (
    _stress_text,
    write_gallery,
)
from services.template_generation.tools.inspect_full_icon_action_gallery import inspect_case


@pytest.fixture
def registry():
    return CardPlanRegistry()


def _policy(registry):
    return {
        "schemaVersion": "full-icon-action-allowlist/1",
        "layoutDigest": template_digest(registry.require_template(LAYOUT_ID)),
        "actionDigest": template_digest(registry.require_template(ACTION_ID)),
        "templates": [{
            "templateId": "BatteryOverviewFull@1", "status": "passed",
            "templateDigest": template_digest(registry.require_template("BatteryOverviewFull@1")),
            "evidence": "review/FI-standard.png",
        }],
    }


@pytest.mark.parametrize(
    "mutation", ["none", "layout", "action", "template", "pending", "evidence"],
)
def test_allowlist_requires_matching_sources_and_passed_evidence(tmp_path, registry, mutation):
    payload = _policy(registry)
    records = payload.get("templates")
    assert isinstance(records, list)
    if mutation == "layout":
        payload["layoutDigest"] = "stale"
    elif mutation == "action":
        payload["actionDigest"] = "stale"
    elif mutation == "template":
        records[0]["templateDigest"] = "stale"
    elif mutation == "pending":
        records[0]["status"] = "pending"
    elif mutation == "evidence":
        records[0]["evidence"] = ""
    (tmp_path / "full-icon-action-allowlist.json").write_text(json.dumps(payload))
    expected = {"BatteryOverviewFull@1"} if mutation == "none" else set()
    assert load_full_icon_action_allowlist(tmp_path, registry.templates) == expected


def test_missing_allowlist_fails_closed(tmp_path, registry):
    assert load_full_icon_action_allowlist(tmp_path, registry.templates) == frozenset()


@pytest.mark.parametrize("template_id", [
    "ScheduleOverviewDateAllDayFull@1",
    "ScheduleOverviewDateEndFull@1",
    "ScheduleOverviewTimezoneDateEndFull@1",
    "ScheduleOverviewTimezoneTimeFull@1",
    "ScheduleOverviewTitleStartFull@1",
    "ScheduleOverviewTitleTimeFull@1",
    "WeatherOverviewAlertInfoFull@1",
    "WeatherOverviewCareAlertFull@1",
    "WeatherOverviewConditionFeelsLikeAlertFull@1",
    "WeatherOverviewDailyDateFull@1",
    "WeatherOverviewDailyHealthFull@1",
    "WeatherOverviewDailyRainFull@1",
    "WeatherOverviewDailyUvColdFull@1",
    "WeatherOverviewFeelsLikeAlertFull@1",
    "WeatherOverviewFull@1",
    "WeatherOverviewHumidityWindFull@1",
    "WeatherOverviewRainWindFull@1",
    "WeatherOverviewTargetDayHealthFull@1",
    "WeatherOverviewUvColdFull@1",
    "WeatherOverviewUvOnlyFull@1",
])
def test_user_approved_templates_reach_candidate_and_compiler(registry, template_id):
    assert template_id in registry.full_icon_action_template_ids
    assert _allows_single_action_template(template_id, registry)
    span = SourceSpan(start=0, end=0)
    business = ParsedCall("template", template_id, ({},), (), span)
    action = ParsedCall("template", ACTION_ID, ({"actionId": "event.call.phone"},), (), span)
    node = ParsedCall("template", LAYOUT_ID, ({},), (business, action), span)
    contract = HybridBodyContract.model_construct(
        allowed_layout_component_ids=("FullIconActionLayout",),
    )
    _validate_ux_layout_root(
        node, contract, size="2x2", registry=registry, embedded_actions=True,
    )


def test_stress_text_reaches_calendar_array_fields_without_changing_value_types():
    title = {"type": "string", "sampleValue": "会议"}
    count = {"type": "integer", "sampleValue": 3}
    flag = {"type": "boolean", "sampleValue": False}
    schema = {"events": [{"title": title, "count": count, "flag": flag}]}
    _stress_text(schema)
    assert title.get("sampleValue") == "会议较长内容用于排版边界检查"
    assert count.get("sampleValue") == 3
    assert flag.get("sampleValue") is False


@pytest.mark.parametrize("approved", [False, True])
def test_planner_and_second_layer_filter_the_same_full_template(registry, approved):
    template_id = "BatteryOverviewFull@1"
    registry.full_icon_action_template_ids = frozenset({template_id} if approved else ())
    group = TemplateBusinessCandidates(
        capabilityId="GetPhoneBatteryInfo", businessId="BatteryOverview", explicitFields=(),
        candidates=(TemplateSearchCandidate(templateId=template_id, coveredExplicitFields=()),),
    )
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetPhoneBatteryInfo": ()})
    plans = _single_business_drafts(
        group, ("event.setPowerSavingMode",), intent, _battery_task(), registry,
    )
    assert bool(plans) is approved
    assert _allows_single_action_template(template_id, registry) is approved
    assert _allows_single_action_template("BatteryOverviewHero@1", registry)
    assert _single_business_drafts(group, (), intent, _battery_task(), registry)


def test_compiler_rejects_unapproved_full_even_when_layout_is_allowed(registry):
    registry.full_icon_action_template_ids = frozenset()
    span = SourceSpan(start=0, end=0)
    business = ParsedCall("template", "BatteryOverviewFull@1", ({},), (), span)
    action = ParsedCall(
        "template", ACTION_ID, ({"actionId": "event.setPowerSavingMode"},), (), span,
    )
    node = ParsedCall("template", LAYOUT_ID, ({},), (business, action), span)
    contract = HybridBodyContract.model_construct(
        allowed_layout_component_ids=("FullIconActionLayout",),
    )
    with pytest.raises(TerselConversionError, match="visually approved"):
        _validate_ux_layout_root(node, contract, size="2x2", registry=registry)


def test_audit_gallery_keeps_unapproved_templates_and_all_states(tmp_path):
    manifest = write_gallery(tmp_path)
    assert manifest.get("templateCount") == 92
    assert manifest.get("counts") == {"success": 270, "not_applicable": 6}
    providers = manifest.get("providers")
    assert isinstance(providers, list)
    cases = providers[0].get("cases")
    assert isinstance(cases, list)
    for case in cases:
        if case.get("status") != "success":
            continue
        filename = case.get("a2uiFile")
        assert isinstance(filename, str)
        messages = json.loads((tmp_path / filename).read_text())
        update = messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        action = next(item for item in components if item.get("id") == "audit_icon_action")
        styles = action.get("styles")
        assert isinstance(styles, dict)
        assert styles.get("width") == 30
        assert styles.get("height") == 30
        parent = next(item for item in components
                      if "audit_icon_action" in item.get("children", []))
        assert parent.get("component") == "Stack"
        assert parent.get("styles", {}).get("alignContent") == "bottomEnd"


@pytest.mark.parametrize("corruption", ["none", "artifact", "dimensions", "geometry_identity"])
def test_capture_verification_rejects_stale_or_mismatched_evidence(tmp_path, corruption):
    source = b"[]"
    (tmp_path / "card.json").write_bytes(source)
    Image.new("RGB", (8, 8)).save(tmp_path / "card.png")
    digest = hashlib.sha256(source).hexdigest()
    case = {"caseId": "case", "targetTemplateId": "ExampleFull@1", "status": "success",
            "a2uiFile": "card.json", "artifactDigest": digest}
    record = {"status": "captured", "artifactDigest": digest, "imageFile": "card.png",
              "width": 8, "height": 8}
    geometry = {"caseId": "case", "cardWidthVp": 150, "cardHeightVp": 150, "nodes": [{
        "id": "audit_icon_action", "type": "Stack",
        "geometry": {"windowOffset": {"x": 5, "y": 5}, "size": {"width": 3, "height": 3}},
    }]}
    if corruption == "artifact":
        record["artifactDigest"] = "old"
    elif corruption == "dimensions":
        record["width"] = 10
    elif corruption == "geometry_identity":
        geometry["caseId"] = "another"
    (tmp_path / "card.geometry.json").write_text(json.dumps(geometry))
    if corruption == "none":
        assert inspect_case(case, record, tmp_path, tmp_path).get("status") == "review_required"
    else:
        with pytest.raises(ValueError, match="mismatch"):
            inspect_case(case, record, tmp_path, tmp_path)
