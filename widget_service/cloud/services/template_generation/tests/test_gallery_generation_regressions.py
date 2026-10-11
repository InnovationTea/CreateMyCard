"""真实画廊批跑暴露的素材、稀疏字段与预留布局回归。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    DataRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
    repair_compact_dsl_binding_paths,
)
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
    template_required_assets_are_available,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
    is_template_compact_dsl,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.test_support.provider_gallery import (
    GalleryInputCase,
    write_gallery_input_dataset,
)
from services.template_generation.test_support.template_examples import append_template_examples


@pytest.fixture
def gallery(tmp_path: Path):
    manifest = write_gallery_input_dataset(tmp_path)
    return tmp_path, manifest


def _case(manifest, template_id: str) -> GalleryInputCase:
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId == template_id:
                return case
    raise AssertionError(f"missing gallery case: {template_id}")


@pytest.mark.parametrize("template_id", [
    "BluetoothDeviceOverviewEarphoneCaseHero@1",
    "BluetoothDeviceOverviewEarphoneHero@1",
    "BluetoothDeviceOverviewCaseConnectionHero@1",
    "BluetoothDeviceOverviewMusicFull@1",
    "WeatherOverviewFeelsLikeWindSupport@1",
])
def test_gallery_candidates_satisfy_required_asset_semantics(gallery, template_id: str):
    root, manifest = gallery
    case = _case(manifest, template_id)
    payload = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
    content = payload.get("content")
    assert isinstance(content, dict)
    ids = content.get("candidateAssetIds")
    assert isinstance(ids, list)
    capabilities_path = (
        Path(__file__).resolve().parents[3]
        / "data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json"
    )
    candidates = []
    for asset in json.loads(capabilities_path.read_text(encoding="utf-8")):
        if asset.get("id") in ids:
            candidates.append(asset)
    definition = get_cardplan_registry().require_template(template_id)
    task = TaskSpec(userQuery=case.targetTemplateDescription, size=case.cardSize,
                    dataModelSchema={}, assetCandidates=candidates)
    assert template_required_assets_are_available(definition, task)


def test_gallery_sample_overrides_only_target_projected_fields(gallery):
    root, manifest = gallery
    for provider in manifest.providers:
        for case in provider.cases:
            payload = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
            content = payload.get("content")
            assert isinstance(content, dict)
            bindings = content.get("candidateDataBindings")
            assert isinstance(bindings, list)
            available: set[str] = set()
            for binding in bindings:
                data_root = binding.get("writeResultTo")
                fields = binding.get("candidateOutputFields")
                assert isinstance(data_root, str)
                assert isinstance(fields, list)
                for field in fields:
                    available.add(data_root.rstrip("/") + field)
            gallery_test = payload.get("galleryTest", {})
            overrides = gallery_test.get("sampleOverrides", {})
            assert set(overrides).issubset(available), case.caseId


def test_gallery_host_metadata_respects_static_limits(gallery):
    root, _ = gallery
    manifest = append_template_examples(root)
    for provider in manifest.providers:
        for case in provider.cases:
            payload = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
            content = payload.get("content")
            assert isinstance(content, dict)
            title = content.get("title")
            description = content.get("description")
            assert isinstance(title, str)
            assert isinstance(description, str)
            assert 0 < len(title) <= 8, case.caseId
            assert 0 < len(description) <= 12, case.caseId


class _SparseTemplateModel:
    def __init__(self, capability_id: str, path: str, template_id: str):
        self.capability_id = capability_id
        self.path = path
        self.template_id = template_id

    async def generate_json(self, _prompt, *, phase):
        assert phase == "template-retrieval-query"
        return {
            "requiredOutputFieldsByCapability": {self.capability_id: [self.path]},
            "action": ["event.open.settings.dnd", "event.open.settings.bluetooth"],
        }

    async def generate(self, _prompt, *_args, **_kwargs):
        content = _prompt[-1].get("content")
        assert isinstance(content, str)
        candidates = None
        for line in content.splitlines():
            if line.startswith("selectedActionCandidates="):
                candidates = json.loads(line.removeprefix("selectedActionCandidates="))
                break
        assert isinstance(candidates, list)
        actions = []
        for candidate in candidates:
            props = {"actionId": candidate.get("actionId"), "label": candidate.get("label")}
            actions.append(f'Template("PillAction@1",{json.dumps(props, ensure_ascii=False)})')
        return (
            'Template("CompactTwoActionLayout@1",{},'
            f'Template("{self.template_id}",{{}}),'
            + ",".join(actions) + ");"
        )


@pytest.mark.parametrize("template_id,path", [
    ("ScheduleOverviewReminderCompact@1", "/events/0/remindTime/0"),
    ("SleepOverviewScoreCompact@1", "/sleepScore"),
])
@pytest.mark.parametrize("missing_required", [False, True])
def test_sparse_template_fields_survive_formal_generation(
    template_id: str, path: str, missing_required: bool,
):
    definition = get_cardplan_registry().require_template(template_id)
    capability_id = definition.capability_id
    data_root = definition.data_domain
    assert capability_id is not None
    assert data_root is not None
    schema = {"data": {}} if missing_required else _build_data_schema(definition)
    task = TaskSpec(
        userQuery=f"按{definition.description}展示",
        size="2x2", dataModelSchema=schema,
        eventCandidates=[
            EventAction(id="event.open.settings.dnd", description="勿扰设置",
                        call="clickToDeeplink", args={}),
            EventAction(id="event.open.settings.bluetooth", description="蓝牙设置",
                        call="clickToDeeplink", args={}),
        ],
    )
    binding = CandidateDataBinding(
        capabilityId=capability_id, writeResultTo=data_root, candidateOutputFields=[path],
    )
    card = {"suggestSize": "2x2", "dataBindings": [binding.model_dump()]}
    operation = generate_template_a2ui(
        task, card, (binding,), _SparseTemplateModel(capability_id, path, template_id),
        trusted_template_candidate_ids=(template_id,),
        trusted_template_action_ids=tuple(event.id for event in task.eventCandidates),
    )
    if missing_required:
        with pytest.raises(TemplateRouteNotApplicable):
            asyncio.run(operation)
    else:
        output = asyncio.run(operation)
        assert template_id in output.template_ids
        assert data_root + path in output.a2ui
        assert output.projected_task_spec.dataModelSchema == task.dataModelSchema


def test_trusted_fallback_preview_does_not_change_normal_search_priority():
    registry = get_cardplan_registry()
    template_id = "BatteryOverviewPercentLevelHero@1"
    definition = registry.require_template(template_id)
    capability_id = definition.capability_id
    data_root = definition.data_domain
    assert capability_id is not None
    assert data_root is not None
    task = TaskSpec(
        userQuery="显示电量文本与电量等级", size="2x2",
        dataModelSchema=_build_data_schema(definition),
    )
    fields = list(definition.required_data)
    binding = CandidateDataBinding(
        capabilityId=capability_id, writeResultTo=data_root, candidateOutputFields=fields,
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={capability_id: fields},
    )
    card = {"dataBindings": [binding.model_dump()]}
    normal = search_template_variants(intent, task, registry, (binding,), card)
    for business in normal.business_candidates:
        assert all(candidate.template_id != template_id for candidate in business.candidates)
    trusted = search_template_variants(
        intent, task, registry, (binding,), card, preferred_template_ids=(template_id,),
    )
    assert trusted.business_candidates[0].candidates[0].template_id == template_id


def test_all_previews_keep_standard_components_through_public_converter():
    cases = build_template_preview_cases()
    assert len(cases) == 184
    for case in cases:
        source = "\n".join(json.dumps(message) for message in case.messages)
        compact = convert_a2ui_to_compact_dsl(source, size=case.size)
        assert is_template_compact_dsl(compact), case.template_id
        rows = parse_compact_dsl_rows(compact)
        assert rows
        assert all(isinstance(row, (ComponentRow, DataRow)) for row in rows)
        repaired = repair_compact_dsl_binding_paths(compact, task_spec={}, card_spec={})
        converted = convert_compact_dsl_to_a2ui(repaired, size=case.size)
        assert [json.loads(line) for line in converted.splitlines()] == list(case.messages)


@pytest.mark.parametrize("marker", ["missing", "orphan", "indirect", "duplicate", "invalid"])
def test_invalid_template_marker_does_not_enable_template_converter(marker):
    root = ["root", "Column", {"width": "100%", "height": "100%"}, ["template_root"]]
    content = ["template_root", "Column", {}, ["image"]]
    image = ["image", "Image", {"src": "resources/base/media/calendar_fill.svg"}]
    rows = [root, content, image]
    if marker == "missing":
        root[3] = ["image"]
        rows = [root, image]
    elif marker == "orphan":
        root[3] = ["image"]
        content[3] = []
    elif marker == "indirect":
        root[3] = ["wrapper"]
        rows.insert(1, ["wrapper", "Column", {}, ["template_root"]])
    elif marker == "duplicate":
        rows.append(["template_root", "Column", {}, []])
    elif marker == "invalid":
        content[2] = {"unsupportedProperty": True}
    compact = "\n".join(json.dumps(row) for row in rows)
    assert not is_template_compact_dsl(compact)


@pytest.mark.parametrize("size,width,height,expected", [
    ("2x2", None, None, False),
    ("2x4", None, None, False),
    ("2x2", 150, 150, False),
    ("2x2", 160, 160, True),
    ("2x4", 300, 150, True),
    ("2x4", 320, 160, False),
    ("2x2", "matchParent", "matchParent", False),
])
def test_template_conversion_route_preserves_legacy_root_dimensions(size, width, height, expected):
    props = {}
    if width is not None:
        props["width"] = width
    if height is not None:
        props["height"] = height
    rows = [
        ["root", "Column", props, ["template_root"]],
        ["template_root", "Column", {}, ["text"]],
        ["text", "Text", {"content": "模板"}],
    ]
    compact = "\n".join(json.dumps(row) for row in rows)
    assert is_template_compact_dsl(compact)
    assert is_template_compact_dsl(compact, size=size) is expected
