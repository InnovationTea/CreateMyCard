"""模板生成模块内部的 artifact 组装逻辑。"""

from __future__ import annotations

import time
import uuid

from app.logger import logger
from models.artifact import ArtifactMeta, GenerationPlan, WidgetArtifact

_MODULE = "[Template Generation]"


def build_template_artifact(
    genui: str,
    card_spec: dict,
    task_spec: dict,
    data_capabilities: list,
    event_candidates: list,
    asset_candidates: list,
    removed: list,
    protocol_profile_id: str,
    protocol_profile_version: str,
    capability_registry_version: str,
    data_bindings: list | None = None,
) -> WidgetArtifact:
    """组装模板路线直接返回所需的完整 artifact。"""
    logger.info(
        f"{_MODULE} artifact_building protocol_profile_id={protocol_profile_id} "
        f"protocol_profile_version={protocol_profile_version} "
        f"capability_registry_version={capability_registry_version} "
        f"data_capability_count={len(data_capabilities)} "
        f"event_candidate_count={len(event_candidates)} "
        f"asset_candidate_count={len(asset_candidates)} removed_count={len(removed)}"
    )
    return WidgetArtifact(
        genui=genui,
        cardSpec=card_spec,
        taskSpec=task_spec,
        effectiveCapabilities={
            "data": [item.id for item in data_capabilities],
            "event": [
                item.model_dump(mode="json", exclude_none=True)
                for item in event_candidates
            ],
            "asset": [item.id for item in asset_candidates],
        },
        removedCapabilities=removed,
        generationPlan=GenerationPlan(
            candidateDataBindings=data_bindings or [],
            candidateEventCandidates=[
                {
                    "capabilityId": item.id,
                    "action": {
                        "call": item.call,
                        "args": item.args,
                    },
                }
                for item in event_candidates
            ],
            candidateAssetIds=[item.id for item in asset_candidates],
        ),
        meta=ArtifactMeta(
            dslProtocolVersion=protocol_profile_version,
            protocolProfileId=protocol_profile_id,
            capabilityRegistryVersion=capability_registry_version,
            generationMode="create",
            artifactId=str(uuid.uuid4()),
            createdAt=int(time.time() * 1000),
        ),
    )
