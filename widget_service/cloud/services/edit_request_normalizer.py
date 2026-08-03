# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass

from api.schemas import CandidateEventCandidate, GenerateWidgetCardRequest
from models.artifact import WidgetArtifact
from models.generation import DEFAULT_WIDGET_SIZE, CardSpec


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
