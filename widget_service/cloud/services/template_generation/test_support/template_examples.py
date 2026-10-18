"""追加经确认的自然语言需求示例；复用正式画廊链路，不直接构造 A2UI。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.template_generation.test_support import provider_gallery as gallery

EXAMPLE_PROVIDER_ID = "gallery.template-examples"
EXAMPLE_PROVIDER_NAME = "模版场景示例"
_CONFIG_PATH = Path(__file__).with_suffix(".json")


class TemplateExample(BaseModel):
    """可审查、可重放的示例输入。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    card_title: str | None = None
    template_id: str
    icon_action: bool = False
    user_query: str
    context: str = ""
    arguments: dict[str, Any]
    fields: list[str]
    samples: dict[str, Any]
    event_ids: list[str]
    asset_ids: list[str] | None = None


def load_template_examples() -> list[TemplateExample]:
    payload = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return [TemplateExample.model_validate(item) for item in payload]


def _object_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"示例请求缺少对象字段：{key}")
    return value


def _example_request(
    input_root: Path,
    base: gallery.GalleryInputCase,
    example: TemplateExample,
    event_capabilities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = json.loads(
        gallery._safe_request_path(input_root, base.requestFile).read_text(encoding="utf-8")
    )
    content = _object_field(payload, "content")
    bindings = content.get("candidateDataBindings")
    if not isinstance(bindings, list) or len(bindings) != 1:
        raise ValueError("场景示例应复用一个单业务绑定")
    binding = bindings[0]
    if not isinstance(binding, dict):
        raise ValueError("场景示例绑定必须是对象")
    root = binding.get("writeResultTo")
    if not isinstance(root, str) or not root.startswith("/data/"):
        raise ValueError("场景示例缺少合法数据根")
    binding.update(arguments=example.arguments, candidateOutputFields=example.fields)
    events = []
    for event_id in example.event_ids:
        event = event_capabilities.get(event_id)
        if event is None:
            raise ValueError(f"示例事件未注册：{event_id}")
        action = _object_field(event, "actionTemplate")
        events.append({"capabilityId": event_id, "action": action})
    query = example.user_query
    if example.context:
        query += "\n补充说明：" + example.context
    content.update(
        title=example.card_title or example.title.split(" ", maxsplit=1)[-1],
        description="模版场景示例，全部为演示数据",
        userQuery=query,
        candidateEventCandidates=events,
    )
    if example.asset_ids is not None:
        registered_assets = gallery._load_asset_capabilities(gallery._CAPABILITY_ROOT)
        for asset_id in example.asset_ids:
            if asset_id not in registered_assets:
                raise ValueError(f"示例素材未注册：{asset_id}")
        content["candidateAssetIds"] = example.asset_ids
    overrides = {}
    for path, value in example.samples.items():
        if path not in example.fields:
            raise ValueError(f"样例字段未声明：{path}")
        overrides[root + path] = value
    payload["galleryTest"] = {"sampleOverrides": overrides}
    _object_field(payload, "utterance")["original"] = example.user_query
    _object_field(payload, "deviceInfo")["time"] = "20260909090000000"
    _object_field(payload, "session")["sessionId"] = "gallery-example-" + example.id
    return payload


def append_template_examples(input_root: Path) -> gallery.GalleryInputManifest:
    """在现有输入清单增加独立页签，重复执行只替换该组。"""
    manifest = gallery.load_gallery_input_manifest(input_root)
    providers = []
    candidates: dict[str, gallery.GalleryInputCase] = {}
    for provider in manifest.providers:
        if provider.providerId == EXAMPLE_PROVIDER_ID:
            continue
        providers.append(provider)
        for case in provider.cases:
            if case.scenarioId.startswith("single-") and case.targetTemplateId:
                candidates[case.targetTemplateId] = case
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    cases = []
    seen_ids: set[str] = set()
    for example in load_template_examples():
        if example.id in seen_ids:
            raise ValueError(f"重复示例：{example.id}")
        seen_ids.add(example.id)
        base = candidates.get(example.template_id)
        if base is None:
            raise ValueError(f"示例目标模板没有画廊输入：{example.template_id}")
        if example.icon_action:
            if not example.template_id.endswith("Full@1") or len(example.event_ids) != 1:
                raise ValueError(f"图标操作示例必须为 Full 加一个操作：{example.id}")
            base = base.model_copy(update={
                "scenarioId": "single-icon-action",
                "scenarioName": "Full + IconAction",
                "expectedLayout": "FullIconActionLayout",
            })
        if len(example.event_ids) != gallery._expected_action_count(base.scenarioId):
            raise ValueError(f"示例操作数量与布局不匹配：{example.id}")
        payload = _example_request(input_root, base, example, events)
        relative = f"providers/template-examples/{example.id}.json"
        path = input_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cases.append(base.model_copy(update={
            "caseId": "template-example-" + example.id,
            "providerId": EXAMPLE_PROVIDER_ID,
            "providerName": EXAMPLE_PROVIDER_NAME,
            "providerSlug": "template-examples",
            "businessName": example.title,
            "scenarioName": "演示数据 · " + base.scenarioName,
            "requestFile": relative,
        }))
    providers.append(gallery.GalleryInputProvider(
        providerId=EXAMPLE_PROVIDER_ID, providerName=EXAMPLE_PROVIDER_NAME,
        providerSlug="template-examples", cases=cases,
    ))
    manifest.providers = providers
    (input_root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return manifest
