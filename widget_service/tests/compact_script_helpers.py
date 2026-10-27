"""静态修正器测试的固定输入；只调用真实转换器及完整产物校验。"""

import json
from dataclasses import replace
from types import SimpleNamespace

from models.artifact import ArtifactMeta, WidgetArtifact
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext, QualityIssue
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator


def options(**changes):
    flags = {
        "enable_compact_script_repair": True,
        "enable_compact_button_slot_repair": True,
        "enable_compact_parent_budget_repair": True,
        "enable_compact_sibling_space_repair": True,
        "enable_compact_duplicate_click_repair": True,
        "enable_compact_height_closure_repair": True,
        "enable_compact_semantic_layout_repair": True,
    }
    return SimpleNamespace(**{**flags, **changes})


def example(text, weight=1):
    rows = [
        [
            "root",
            "Stack",
            {"width": "matchParent", "height": "matchParent", "borderRadius": 20, "clip": True},
            ["foreground"],
        ],
        [
            "foreground",
            "Column",
            {"width": "matchParent", "height": "matchParent", "padding": 12},
            ["row"],
        ],
        ["row", "Row", {"width": "matchParent", "height": 60, "itemMargin": 12}, ["left", "right"]],
        ["left", "Column", {"layoutWeight": weight}, ["value"]],
        ["right", "Column", {"layoutWeight": 1}, ["label"]],
        ["value", "EmphasisText", {"mainText": text}],
        ["label", "EmphasisText", {"mainText": "正常"}],
        ["/ui/state", "ready"],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def process(source):
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    task = {
        "size": "2x4",
        "appVersion": "11.7.7.300",
        "dataModelSchema": {"data": {}},
        "userQuery": "展示两组静态文字",
        "eventCandidates": [],
        "assetCandidates": [],
    }
    card = {"title": "静态修复回归", "description": "静态文字布局", "suggestSize": "2x4"}
    context = DslProcessingContext(
        size="2x4",
        task_spec=task,
        card_spec=card,
        protocol_profile=profile,
        layout_scope="W-plan-guided",
        colorless_layout=True,
    )
    result = DesignCompactProcessor().process(source, context)
    if result.errors:
        return result
    artifact = WidgetArtifact(
        genui=result.standard_dsl,
        cardSpec=card,
        taskSpec=task,
        effectiveCapabilities={"data": [], "event": [], "asset": []},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="app-11.7.7.300_rom-7.0",
            createdAt=0,
        ),
    )
    errors = ArtifactValidator().validate_layout(artifact, profile)
    issues = tuple(QualityIssue("validation", "ARTIFACT", error) for error in errors)
    return replace(result, issues=(*result.issues, *issues))
