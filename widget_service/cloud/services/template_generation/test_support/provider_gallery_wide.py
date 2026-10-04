"""在现有正式画廊输入上追加宽卡与版本外观，不改变生产路由。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from services.template_generation.controls import TemplateControls

from .provider_gallery import (
    FUSION_PRD_VERSION,
    BusinessDefinition,
    GalleryAppearance,
    GalleryInputCase,
    GalleryInputProvider,
    GalleryTemplatePair,
    GalleryTemplateSelection,
    _kebab_case,
    _paired_missing_reason,
    _paired_request_envelope,
    _request_envelope,
)

PLAIN_PRD_VERSION = "11.7.5.205"
_HIGH_VERSION = GalleryAppearance("fusion", "高版本", FUSION_PRD_VERSION, True)
_WIDE_SCENARIOS = {
    "WideFull": ("wide-content", "单内容", "WideFullOnlyLayout"),
    "WideHero": ("wide-one-action", "单内容 + 1 个操作", "WideSingleFocusLayout"),
    "WideHalf": ("wide-two-half", "上下双内容", "WideTwoHalfLayout"),
}


def _write_request(root: Path, case: GalleryInputCase, payload: dict[str, Any]) -> None:
    path = root / case.requestFile
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _half_partner(
    selection: GalleryTemplateSelection, definitions: list[BusinessDefinition],
) -> GalleryTemplateSelection:
    for business in definitions:
        if business.capability_id == selection.business.capability_id:
            continue
        for template in business.templates:
            if template.suffix == "WideHalf":
                return GalleryTemplateSelection(business, template)
    raise ValueError(f"WideHalf 缺少独立业务搭档：{selection.template.template_id}")


def _wide_case(
    root: Path, selection: GalleryTemplateSelection, partner: GalleryTemplateSelection,
    event_capabilities: dict[str, dict[str, Any]],
    asset_capabilities: dict[str, dict[str, Any]], missing_reason: str,
    fusion_business_ids: set[str],
) -> GalleryInputCase:
    business = selection.business
    template = selection.template
    metadata = _WIDE_SCENARIOS.get(template.suffix)
    if metadata is None:
        raise ValueError(f"unsupported wide template: {template.template_id}")
    scenario_id, scenario_name, layout = metadata
    is_half = template.suffix == "WideHalf"
    if is_half:
        payload = _paired_request_envelope(
            GalleryTemplatePair(selection, partner), _HIGH_VERSION,
            event_capabilities, asset_capabilities,
        )
    else:
        original_scenario = (
            "single-one-action" if template.suffix == "WideHero" else "single-content"
        )
        payload = _request_envelope(
            business, template, original_scenario, _HIGH_VERSION,
            event_capabilities, asset_capabilities,
        )
    content = payload.get("content")
    if not isinstance(content, dict):
        raise ValueError("gallery request content must be an object")
    query = content.get("userQuery")
    if not isinstance(query, str):
        raise ValueError("gallery request userQuery must be a string")
    query = query.replace("2×2", "2×4")
    if is_half:
        query = (
            f"生成一个2×4卡片，上下各一块全宽半高内容，分别展示“{template.description}”"
            f"和“{partner.template.description}”，两个业务都必须保留，不显示操作按钮。"
        )
        content["candidateEventCandidates"] = []
    content["size"] = "2x4"
    content["userQuery"] = query
    payload["utterance"] = {"original": query, "type": "text"}
    slug = _kebab_case(template.template_id)
    case_id = f"{business.provider_slug}__2x4__{slug}__{scenario_id}__fusion"
    payload["session"] = {"sessionId": f"gallery-{case_id}", "interactionId": "1", "isNew": True}
    expects_fusion = template.suffix == "WideFull" and business.business_id in fusion_business_ids
    case = GalleryInputCase(
        caseId=case_id, cardSize="2x4", providerId=business.provider_id,
        providerName=business.provider_name, providerSlug=business.provider_slug,
        businessId=business.business_id, businessName=business.business_name,
        scenarioId=scenario_id, scenarioName=f"高版本 · {scenario_name}",
        appearanceId="fusion", appearanceName="高版本", prdVer=FUSION_PRD_VERSION,
        expectsFusionBall=expects_fusion, expectedLayout=layout,
        expectedTemplateSuffix=template.suffix, targetTemplateId=template.template_id,
        targetTemplateDescription=template.description,
        partnerTemplateId=partner.template.template_id if is_half else "",
        requestFile=f"providers/{business.provider_slug}/2x4/{slug}/fusion/{scenario_id}.json",
        missingReason=missing_reason,
    )
    _write_request(root, case, payload)
    return case


def _plain_case(root: Path, original: GalleryInputCase) -> GalleryInputCase:
    case = original.model_copy(deep=True)
    case.caseId = original.caseId.removesuffix("__fusion") + "__plain"
    case.appearanceId = "plain"
    case.appearanceName = "非融球"
    case.prdVer = PLAIN_PRD_VERSION
    case.expectsFusionBall = False
    case.scenarioName = "非融球 · " + original.scenarioName.split(" · ", maxsplit=1)[-1]
    case.requestFile = original.requestFile.replace("/fusion/", "/plain/")
    if case.requestFile == original.requestFile:
        raise ValueError(f"gallery request has no fusion path segment: {original.requestFile}")
    payload = deepcopy(json.loads((root / original.requestFile).read_text(encoding="utf-8")))
    device_info = payload.get("deviceInfo")
    session = payload.get("session")
    if not isinstance(device_info, dict) or not isinstance(session, dict):
        raise ValueError("gallery request requires deviceInfo and session objects")
    device_info["prdVer"] = PLAIN_PRD_VERSION
    session["sessionId"] = f"gallery-{case.caseId}"
    _write_request(root, case, payload)
    return case


def extend_gallery_inputs(
    root: Path, providers: list[GalleryInputProvider], definitions: list[BusinessDefinition],
    controls: TemplateControls, data_capability_ids: set[str],
    event_capabilities: dict[str, dict[str, Any]], asset_capabilities: dict[str, dict[str, Any]],
    fusion_business_ids: set[str], *, card_sizes: tuple[str, ...], appearances: tuple[str, ...],
) -> list[GalleryInputProvider]:
    """宽模板各生成一次；半高模板使用独立业务的半高搭档。"""
    by_provider = {provider.providerId: provider for provider in providers}
    if "2x2" not in card_sizes:
        for provider in providers:
            provider.cases = []
    if "2x4" in card_sizes:
        for business in definitions:
            provider = by_provider.get(business.provider_id)
            if provider is None:
                raise ValueError(f"gallery provider missing: {business.provider_id}")
            for template in business.templates:
                if template.suffix not in _WIDE_SCENARIOS:
                    continue
                selection = GalleryTemplateSelection(business, template)
                partner = selection
                if template.suffix == "WideHalf":
                    partner = _half_partner(selection, definitions)
                reason = _paired_missing_reason(
                    GalleryTemplatePair(selection, partner), controls, data_capability_ids,
                )
                case = _wide_case(
                    root, selection, partner, event_capabilities, asset_capabilities,
                    reason, fusion_business_ids,
                )
                provider.cases.append(case)
    result: list[GalleryInputProvider] = []
    for provider in providers:
        expanded: list[GalleryInputCase] = []
        for case in provider.cases:
            if "fusion" in appearances:
                expanded.append(case)
            if "plain" in appearances:
                expanded.append(_plain_case(root, case))
        provider.cases = expanded
        if expanded:
            result.append(provider)
    return result
