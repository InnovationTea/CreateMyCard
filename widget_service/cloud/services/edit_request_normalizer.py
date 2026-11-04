# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass

from api.schemas import CandidateEventCandidate, GenerateWidgetCardRequest
from models.artifact import WidgetArtifact
from models.generation import DEFAULT_WIDGET_SIZE, CardSpec
from services.post_layout_theme_registry import registered_themes


@dataclass(frozen=True)
class EditNormalizationResult:
    request: GenerateWidgetCardRequest
    inherited_categories: tuple[str, ...]
    replaced_categories: tuple[str, ...]


class EditRequestNormalizer:
    """按字段省略/替换语义构造完整的 create 或 edit 请求。"""

    @staticmethod
    def normalize_create(request: GenerateWidgetCardRequest) -> GenerateWidgetCardRequest:
        return request.model_copy(
            update={
                "size": request.size or DEFAULT_WIDGET_SIZE,
                "candidateDataBindings": request.candidateDataBindings or [],
                "candidateEventCandidates": request.candidateEventCandidates or [],
                "candidateAssetIds": request.candidateAssetIds or [],
            }
        )

    def normalize_edit(
        self,
        request: GenerateWidgetCardRequest,
        source_artifact: WidgetArtifact,
    ) -> EditNormalizationResult:
        card_spec = CardSpec(**source_artifact.cardSpec)
        plan = source_artifact.generationPlan
        inherited: list[str] = []
        replaced: list[str] = []

        values = {
            "size": card_spec.suggestSize,
            "title": card_spec.title,
            "description": card_spec.description,
            "candidateDataBindings": list(plan.candidateDataBindings),
            "candidateEventCandidates": [
                CandidateEventCandidate(**item) for item in plan.candidateEventCandidates
            ],
            "candidateAssetIds": list(plan.candidateAssetIds),
        }
        for field_name in values:
            if field_name in request.model_fields_set:
                values[field_name] = getattr(request, field_name)
                replaced.append(field_name)
            else:
                inherited.append(field_name)

        return EditNormalizationResult(
            request=request.model_copy(update=values),
            inherited_categories=tuple(inherited),
            replaced_categories=tuple(replaced),
        )


def normalize_source_theme_echo(
    request: GenerateWidgetCardRequest, source: WidgetArtifact,
) -> GenerateWidgetCardRequest:
    """仅移除可证明来自原卡的冗余主题项；不修复真实候选变更。"""
    original = source.generationPlan.candidateAssetIds
    supplied = request.candidateAssetIds
    if supplied is None or supplied == original:
        return request
    if len(set(supplied)) != len(supplied):
        return request
    registered = set()
    for theme in registered_themes(include_disabled=True):
        registered.add(theme.get("id"))
    effective = source.effectiveCapabilities.get("asset", [])
    declared = source.taskSpec.get("assetCandidates", [])
    if not isinstance(declared, list):
        return request
    allowed = set()
    for item in declared:
        if not isinstance(item, dict):
            continue
        identity = item.get("id")
        address = item.get("src")
        if not isinstance(identity, str) or not isinstance(address, str):
            continue
        if identity in registered and identity in effective and address.strip():
            allowed.add(identity)
    retained = []
    for identity in supplied:
        if identity in original or identity not in allowed:
            retained.append(identity)
    normalized = request
    if retained == original:
        normalized = request.model_copy(update={"candidateAssetIds": list(original)})
    return normalized
