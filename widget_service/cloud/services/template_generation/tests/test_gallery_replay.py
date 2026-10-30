"""失败画廊的原始四业务提示预算、时间配对和重跑状态回归。"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced import ux_mixed_prompt
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    UxMixedPromptProjection,
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan.prompt_guidance import selected_template_guidance
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.test_support.gallery_replay import (
    normalize_gallery_case,
    prepare_failed_replay,
)


def _load_fixtures() -> list[dict]:
    path = Path(__file__).parent / "fixtures/gallery_failed_plans.json"
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    selected = []
    for fixture in fixtures:
        if fixture.get("index") != 34:
            selected.append(fixture)
    return selected


_FIXTURES = _load_fixtures()


def _required(mapping, key):
    value = mapping.get(key)
    assert value is not None, key
    return value


def test_title_location_gallery_marks_removed_wide_pair_inapplicable_for_fresh_and_replay(tmp_path):
    manifest = gallery.write_gallery_input_dataset(tmp_path)
    matches = []
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId == "ScheduleOverviewTitleLocationHero@1":
                matches.append(case)
    assert len(matches) == 1
    case = matches[0]
    payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
    original_id = case.caseId
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    legacy_case = case.model_copy(update={
        "cardSize": "2x2", "partnerTemplateId": "", "compositionTemplateIds": [],
        "expectedLayout": "HeroActionLayout", "expectedActionCount": 1,
        "constrainLayout": False, "expectsFusionBall": True, "scenarioId": "single-one-action",
    })
    normalized, replay = normalize_gallery_case(legacy_case, payload, events)
    assert normalized == case
    assert replay == payload
    assert normalized.caseId == original_id
    assert normalized.cardSize == "2x4"
    assert normalized.expectedLayout == "WideTwoFocusLayout"
    assert normalized.compositionTemplateIds == [
        "ScheduleOverviewTitleLocationHero@1", "WeatherOverviewConditionHero@1",
    ]
    assert normalized.expectedActionCount == 0
    assert "无动作双 Hero 布局已移除" in normalized.notApplicableReason
    assert normalized.constrainLayout
    content = _required(payload, "content")
    assert content.get("size") == "2x4"
    assert content.get("candidateEventCandidates") == []
    bindings = _required(content, "candidateDataBindings")
    assert len(bindings) == 2
    assert bindings[0].get("candidateOutputFields") == [
        "/events/0/title", "/events/0/eventLocation",
    ]
    assert bindings[1].get("candidateOutputFields") == ["/current/condition"]


def _build_failed_wide_prompt(fixture) -> UxMixedPromptProjection:
    task_payload = deepcopy(_required(fixture, "task"))
    decision = deepcopy(_required(fixture, "decision"))
    # 第 33 项同时存在样例动作映射错误；生产输入归一化单独验证。
    if fixture.get("index") == 33:
        for action in task_payload.get("eventCandidates", []):
            if action.get("id") == "event.open.health.sportsRecord":
                action["id"] = "event.open.health.activityRecord"
        decision["action"] = ["event.open.health.activityRecord"]
    task = TaskSpec.model_validate(task_payload)
    card = _required(fixture, "card")
    bindings = tuple(
        CandidateDataBinding.model_validate(item) for item in _required(fixture, "bindings")
    )
    intent = TemplateSearchIntent.model_validate(decision)
    registry = get_cardplan_registry()
    case = _required(fixture, "case")
    found = search_template_variants(
        intent, task, registry, bindings, card,
        preferred_template_ids=tuple(_required(case, "compositionTemplateIds")),
    )
    layout_id = _required(case, "expectedLayout") + "@1"
    plans = plan_template_candidates(
        intent, found, task, registry, candidate_bindings=bindings, allowed_layout_ids=(layout_id,),
    )
    assert plans
    assert all(plan.layout_template_id == layout_id for plan in plans)
    return build_ux_mixed_prompt(
        task_spec=task, card_spec=card, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda item: str(item.get("index")))
def test_original_failed_wide_plans_fit_prompt_budget(fixture) -> None:
    projection = _build_failed_wide_prompt(fixture)
    assert sum(len(message.get("content", "")) for message in projection.messages) <= 64_000


@pytest.mark.parametrize("prompt_chars", [24_001, 64_000, 64_001])
def test_prompt_budget_keeps_complete_messages_and_rejects_overflow(
    monkeypatch: pytest.MonkeyPatch, prompt_chars: int,
) -> None:
    fixture = _FIXTURES[0]
    original = _build_failed_wide_prompt(fixture)
    original_chars = sum(len(message.get("content", "")) for message in original.messages)
    assert original_chars < prompt_chars
    expanded_kernel = (
        ux_mixed_prompt.UX_MIXED_SYSTEM_PROMPT_KERNEL + "约" * (prompt_chars - original_chars)
    )
    monkeypatch.setattr(ux_mixed_prompt, "UX_MIXED_SYSTEM_PROMPT_KERNEL", expanded_kernel)

    if prompt_chars > 64_000:
        with pytest.raises(
            ValueError,
            match=(
                rf"UX Mixed Prompt exceeds the service input budget: total={prompt_chars}, "
                r"limit=64000, provider_rules=\d+, plans=\d+"
            ),
        ):
            _build_failed_wide_prompt(fixture)
    else:
        expanded = _build_failed_wide_prompt(fixture)
        assert expanded.messages == [
            {"role": "system", "content": expanded_kernel},
            original.messages[1],
        ]
        assert sum(len(message.get("content", "")) for message in expanded.messages) == prompt_chars
        assert expanded.contract == original.contract
        assert expanded.requested_template_ids == original.requested_template_ids


def test_guidance_keeps_complete_selected_shared_and_unknown_blocks() -> None:
    content = (
        "# 规则\n公共字段约束。\n"
        "- Alpha@1 的字段。\n  续行必须保留。\n"
        "- Beta@1 的专属字段。\n  不应泄漏。\n"
        "- Alpha@1 与 Beta@1 共用约束。\n"
        "- WideLayout@1 的骨架约束。\n"
        "- 禁止新增字段。\n"
    )
    actual = selected_template_guidance(
        content, frozenset({"Alpha@1", "Beta@1"}), frozenset({"Alpha@1"}),
    )
    assert "公共字段约束" in actual
    assert "续行必须保留" in actual
    assert "Beta@1 的专属" not in actual
    assert "不应泄漏" not in actual
    assert "Alpha@1 与 Beta@1 共用约束" in actual
    assert "WideLayout@1 的骨架约束" in actual
    assert "禁止新增字段" in actual


def test_guidance_preserves_public_paragraphs_but_keeps_indented_item_continuations() -> None:
    content = (
        "# 规则\n\n"
        "- Alpha@1 的专属字段。\n\n"
        "  缩进续行仍是 Alpha 的要求。\n\n"
        "Beta@1 示例后的独立公共段落。\n"
        "公共规则的第二行。\n\n"
        "- Gamma@1 的字段。\n\n"
        "  Gamma 续行必须完整保留。\n"
    )
    actual = selected_template_guidance(
        content, frozenset({"Alpha@1", "Beta@1", "Gamma@1"}), frozenset({"Gamma@1"}),
    )
    assert "Alpha" not in actual
    assert "Beta@1 示例后的独立公共段落。\n公共规则的第二行。" in actual
    assert "- Gamma@1 的字段。\n\n  Gamma 续行必须完整保留。" in actual


@pytest.mark.parametrize(
    "template_id",
    [
        "BluetoothDeviceOverviewHero@1",
        "BluetoothDeviceOverviewEarbudPairCompact@1",
        "BluetoothDeviceOverviewEarbudPairFull@1",
    ],
)
def test_earphone_guidance_preserves_complete_shared_title_and_connection_rules(
    template_id: str,
) -> None:
    registry = get_cardplan_registry()
    component_ids = ("BluetoothDeviceOverview",)
    full = registry.provider_second_layer_guidance(component_ids)
    full_content = _required(full[0], "content")
    title_rule = "支持 title 的上述模板必须逐字传入非空 cardComposition.businessTitleCandidate"
    shared_paragraph = next(
        paragraph for paragraph in full_content.split("\n\n") if title_rule in paragraph
    )
    assert "耳机名称与连接状态同时存在时" in shared_paragraph
    filtered = registry.provider_second_layer_guidance(
        component_ids, selected_template_ids=(template_id,),
    )
    actual = _required(filtered[0], "content")
    assert shared_paragraph in actual
    assert "BluetoothDeviceOverviewEarbudPairRingFull@1" not in actual


def test_fresh_and_replayed_inputs_keep_not_applicable_cases(tmp_path: Path) -> None:
    original_root = tmp_path / "original"
    manifest = gallery.write_gallery_input_dataset(original_root)
    cases = []
    for provider in manifest.providers:
        for case in provider.cases:
            cases.append({"caseId": case.caseId, "status": "failed"})
    results = tmp_path / "results"
    results.mkdir()
    (results / "manifest.json").write_text(
        json.dumps({"providers": [{"cases": cases}]}), encoding="utf-8",
    )
    output = tmp_path / "replay"
    prepare_failed_replay(original_root, results, output)
    replay = gallery.load_gallery_input_manifest(output)
    replay_cases = []
    for provider in replay.providers:
        replay_cases.extend(provider.cases)
    assert len(replay_cases) == len(cases)
    unavailable = [case for case in replay_cases if case.notApplicableReason]
    assert len(unavailable) == 4
    assert {case.caseId for case in replay_cases} == {case.get("caseId") for case in cases}
    for provider in manifest.providers:
        for case in provider.cases:
            source = json.loads((original_root / case.requestFile).read_text(encoding="utf-8"))
            target = json.loads((output / case.requestFile).read_text(encoding="utf-8"))
            assert source == target


def test_replay_restores_external_coverage_metadata(tmp_path: Path) -> None:
    """旧主干输入模型没有扩展字段，原批跑将它们保存在结果清单。"""
    from services.template_generation.test_support.wide_compositions import append_wide_compositions

    input_root = tmp_path / "inputs"
    gallery.write_gallery_input_dataset(input_root)
    manifest = append_wide_compositions(input_root)
    provider = manifest.providers[0]
    case = next(
        item for item in provider.cases if item.expectedLayout == "WideFourCompactLayout"
    )
    result = case.model_dump()
    result["status"] = "failed"
    before = case.model_copy(deep=True)
    case.compositionTemplateIds = []
    case.constrainLayout = False
    case.expectedActionCount = None
    provider.cases = [case]
    manifest.providers = [provider]
    (input_root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    (results / "manifest.json").write_text(
        json.dumps({"providers": [{"cases": [result]}]}), encoding="utf-8",
    )
    output = tmp_path / "replay"
    prepare_failed_replay(input_root, results, output)
    actual = gallery.load_gallery_input_manifest(output).providers[0].cases[0]
    assert actual.caseId == before.caseId
    assert actual.compositionTemplateIds == before.compositionTemplateIds
    assert len(actual.compositionTemplateIds) == 4
    assert actual.constrainLayout
    assert actual.expectedActionCount == 0


@pytest.mark.asyncio
async def test_not_applicable_runner_skips_model_even_without_dry_run(tmp_path: Path) -> None:
    from services.template_generation.tests.test_provider_gallery_batch import _GalleryService

    manifest = gallery.write_gallery_input_dataset(tmp_path / "inputs")
    for provider in manifest.providers:
        provider.cases = [case for case in provider.cases if case.notApplicableReason]
    (tmp_path / "inputs/manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8",
    )
    service = _GalleryService()
    summary = await gallery.ProviderGalleryBatchRunner(service).run(
        tmp_path / "inputs", tmp_path / "output",
    )
    assert summary.total == summary.not_applicable == 4
    assert summary.failed == summary.success == 0
    assert not service.requests


def test_activity_replay_uses_registered_action_without_mutating_source(tmp_path: Path) -> None:
    manifest = gallery.write_gallery_input_dataset(tmp_path)
    sample = None
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId == "ActivityOverviewFull@1":
                sample = case
                break
    assert sample is not None
    source = json.loads((tmp_path / sample.requestFile).read_text(encoding="utf-8"))
    content = _required(source, "content")
    content["candidateEventCandidates"] = [{"capabilityId": "event.open.health.sportsRecord"}]
    content["userQuery"] = "显示活动摘要，打开锻炼"
    before = deepcopy(source)
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    _, normalized = normalize_gallery_case(sample, source, events)
    assert source == before
    actual = _required(normalized, "content")
    event = _required(actual, "candidateEventCandidates")[0]
    assert event.get("capabilityId") == "event.open.health.activityRecord"
    assert actual.get("userQuery") == "显示活动摘要，打开活动记录"


def test_time_sample_is_format_valid_and_preserves_explicit_override() -> None:
    from services.template_generation.test_support.gallery_replay import _normalize_time_samples

    content = {"candidateDataBindings": [{
        "capabilityId": "GetCurrentTime", "writeResultTo": "/data/currentTime",
        "candidateOutputFields": ["/currentDate", "/dayOfWeek"],
    }]}
    payload = {"galleryTest": {"sampleOverrides": {"/data/currentTime/dayOfWeek": "星期三"}}}
    _normalize_time_samples(payload, content)
    samples = gallery._gallery_sample_overrides_from_envelope(payload)
    assert samples.get("/data/currentTime/currentDate") == "2026-10-20"
    assert samples.get("/data/currentTime/dayOfWeek") == "星期三"
    assert "/data/currentTime/updatedAt" not in samples
