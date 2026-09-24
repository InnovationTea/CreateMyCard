"""Q059：通过正式组合链路生成 Full 与两个 CompactAction 的本地预览。"""

import json
from pathlib import Path

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    _set_path,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.pipeline import generate_template_a2ui

TEMPLATE_ID = "BluetoothDeviceOverviewMusicFull@1"


async def generate(source: Path, output: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    content = payload.get("content", payload)
    registry = CardPlanRegistry()
    definition = registry.require_template(TEMPLATE_ID)
    asset_file = Path(__file__).resolve().parents[4] / (
        "data/capabilities/app-11.7.7.300_rom-7.0/asset_capabilities.json"
    )
    catalog = json.loads(asset_file.read_text(encoding="utf-8"))
    assets = [item for item in catalog if item.get("id") in content.get("candidateAssetIds", [])]
    events = []
    for candidate in content.get("candidateEventCandidates", []):
        action = candidate.get("action")
        assert isinstance(action, dict)
        event_id = candidate.get("capabilityId")
        events.append(EventAction(id=event_id, **action))
    schema = _build_data_schema(definition)
    _set_path(
        schema,
        definition.data_domain.rstrip("/") + "/updatedAt",
        {"type": "string", "sampleValue": "14:00"},
    )
    task = TaskSpec(
        userQuery=content.get("userQuery"),
        size="2x4",
        eventCandidates=events,
        assetCandidates=assets,
        dataModelSchema=schema,
    )
    bindings = tuple(
        CandidateDataBinding.model_validate(item)
        for item in content.get("candidateDataBindings", [])
    )

    class LocalModel:
        async def generate_json(self, _prompt, *, phase):
            assert phase == "template-retrieval-query"
            return {
                "requiredOutputFieldsByCapability": {
                    "GetEarphoneInfo": bindings[0].candidateOutputFields,
                },
                "action": [event.id for event in events],
            }

        async def generate(self, prompt, _profile, **_kwargs):
            assert TEMPLATE_ID in str(prompt)
            return (
                'Template("WideFullTwoCompactLayout@1",{"compactRows":true},'
                f'Template("{TEMPLATE_ID}",'
                '{"caseIcon":"resources/base/media/earphone_case_16644.svg"}),'
                'Template("CompactAction@1",{"actionId":"event.open.settings.bluetooth",'
                '"label":"蓝牙设置","icon":"resources/base/media/icon_earphone.svg",'
                '"prominent":true}),'
                'Template("CompactAction@1",{"actionId":"event.open.music.daily",'
                '"label":"每日推荐","icon":"resources/base/media/music_fill.svg",'
                '"prominent":true}));'
            )

    result = await generate_template_a2ui(
        task,
        {"suggestSize": "2x4", "dataBindings": [item.model_dump() for item in bindings]},
        bindings,
        LocalModel(),
    )
    messages = [json.loads(line) for line in result.a2ui.splitlines() if line.strip()]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(messages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Q059 Full + CompactAction + CompactAction compiled")
