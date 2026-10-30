"""宽卡垂域组合的可重放输入和骨架筛选边界。"""

import json
from pathlib import Path

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    search_template_variants,
    template_required_assets_are_available,
)
from services.template_generation.engine.cardplan.wide_template_planner import (
    _template_intrinsic_height,
)
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.test_support.wide_compositions import (
    _selections,
    append_wide_compositions,
    composition_layouts,
)
from services.template_generation.tests.test_wide_template_planner import _health_case


def test_compositions_stay_in_original_domain_and_preserve_existing_requests(
    tmp_path: Path,
) -> None:
    original = gallery.write_gallery_input_dataset(tmp_path)
    original_ids = [provider.providerId for provider in original.providers]
    requests = {}
    for provider in original.providers:
        for case in provider.cases:
            requests[case.caseId] = (case.requestFile, (tmp_path / case.requestFile).read_bytes())
    manifest = append_wide_compositions(tmp_path)
    assert [provider.providerId for provider in manifest.providers] == original_ids
    selections = _selections()
    assets = gallery._load_asset_capabilities(gallery._CAPABILITY_ROOT)
    registry = get_cardplan_registry(True)
    layouts = {layout.layout_id: layout for layout in composition_layouts()}
    covered = set()
    composition_count = 0
    for provider in manifest.providers:
        for case in provider.cases:
            before = requests.get(case.caseId)
            if before is not None:
                assert case.requestFile == before[0]
                assert (tmp_path / case.requestFile).read_bytes() == before[1]
                continue
            composition_count += 1
            covered.add(case.expectedLayout)
            assert case.cardSize == "2x4"
            assert case.prdVer == gallery.FUSION_PRD_VERSION
            assert case.constrainLayout
            layout = layouts.get(case.expectedLayout)
            assert layout is not None
            assert len(case.compositionTemplateIds) == len(layout.roles)
            assert case.expectedActionCount == len(layout.action_templates)
            if case.expectedLayout == "WideHeroCompactLayout":
                assert case.expectedActionCount == 1
                assert layout.roles == ("Hero", "Compact")
                assert layout.action_owners == (0,)
            if case.expectedLayout == "WideFullCompactLayout":
                assert case.expectedActionCount == 0
                assert layout.roles == ("Full", "Compact")
            domains = []
            payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
            content = payload.get("content")
            assert isinstance(content, dict)
            asset_ids = content.get("candidateAssetIds")
            assert isinstance(asset_ids, list)
            asset_candidates = []
            for asset_id in asset_ids:
                asset = assets.get(asset_id)
                assert asset is not None
                asset_candidates.append(asset)
            task = TaskSpec(
                userQuery="宽卡素材检查", size="2x4",
                dataModelSchema={}, assetCandidates=asset_candidates,
            )
            for position, template_id in enumerate(case.compositionTemplateIds):
                selection = selections.get(template_id)
                assert selection is not None
                domains.append(selection.business.provider_slug)
                assert template_required_assets_are_available(
                    registry.require_template(template_id), task,
                )
                if layout.slot_height_budgets:
                    budget = layout.slot_height_budgets[position]
                    if budget is not None:
                        assert _template_intrinsic_height(template_id, registry) <= budget
            assert domains[0] == provider.providerSlug
            assert len(domains) == len(set(domains))
    assert covered == set(layouts)
    assert composition_count == 74
    audit = json.loads((tmp_path / "wide-composition-selection.json").read_text(encoding="utf-8"))
    excluded = audit.get("excluded")
    assert isinstance(excluded, list)
    # 现有电量 Hero 不满足该骨架高度预算，不用缺少手机图标的模板补足数量。
    assert any(
        (item.get("domain"), item.get("layout")) == ("battery", "WideTwoHeroActionLayout")
        for item in excluded
    )
    first = manifest.model_dump()
    replay = append_wide_compositions(tmp_path)
    assert replay.model_dump() == first
    assert append_wide_compositions(tmp_path, seed=20261015).model_dump() != first


def test_layout_constraint_filters_legal_plans_and_rejects_incompatible_skeleton() -> None:
    task, bindings, card, intent = _health_case(include_countdown=True)
    registry = get_cardplan_registry()
    found = search_template_variants(intent, task, registry, bindings, card)
    original = plan_template_candidates(intent, found, task, registry)
    target = original[0].layout_template_id
    selected = plan_template_candidates(intent, found, task, registry, allowed_layout_ids=(target,))
    assert selected
    assert all(plan.layout_template_id == target for plan in selected)
    default = plan_template_candidates(intent, found, task, registry, allowed_layout_ids=())
    assert default == original
    with pytest.raises(TemplateRetrievalMiss, match="supported atomic plan"):
        plan_template_candidates(
            intent,
            found,
            task,
            registry,
            allowed_layout_ids=("WideSingleFocusLayout@1",),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["none", "layout", "business"])
async def test_runner_passes_all_businesses_and_checks_actual_skeleton(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    from types import SimpleNamespace

    from services.template_generation import facade
    from services.template_generation.tests.test_provider_gallery_batch import _GalleryService

    gallery.write_gallery_input_dataset(tmp_path)
    manifest = append_wide_compositions(tmp_path)
    provider = manifest.providers[0]
    case = next(item for item in provider.cases if item.expectedLayout == "WideFourCompactLayout")
    provider.cases = [case]
    manifest.providers = [provider]
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    async def engine():
        layout = "WideTwoFullLayout" if mismatch == "layout" else case.expectedLayout
        templates = case.compositionTemplateIds
        if mismatch == "business":
            templates = templates[:-1]
        return SimpleNamespace(template_ids=(layout + "@1", *templates))

    monkeypatch.setattr(facade, "generate_template_engine_a2ui", engine)

    class Service(_GalleryService):
        async def generate_widget_card_terse_dsl_nested2(
            self,
            request,
            *,
            trusted_template_layout_ids=(),
            **kwargs,
        ):
            assert trusted_template_layout_ids == (case.expectedLayout + "@1",)
            assert kwargs.get("trusted_template_candidate_ids") == tuple(
                case.compositionTemplateIds
            )
            await facade.generate_template_engine_a2ui()
            return await super().generate_widget_card_terse_dsl_nested2(request, **kwargs)

    summary = await gallery.ProviderGalleryBatchRunner(Service()).run(tmp_path, tmp_path / "out")
    output = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    providers = output.get("providers")
    assert isinstance(providers, list)
    cases = providers[0].get("cases")
    assert isinstance(cases, list)
    result = cases[0]
    if mismatch != "none":
        assert summary.failed == 1
        expected_error = "骨架不匹配" if mismatch == "layout" else "组合缺少业务模板"
        assert expected_error in result.get("errorMessage", "")
    else:
        assert summary.success == 1
        assert result.get("actualLayout") == case.expectedLayout
        assert result.get("compositionTemplateIds") == case.compositionTemplateIds
        assert len(result.get("actualTemplateIds", [])) == 5
