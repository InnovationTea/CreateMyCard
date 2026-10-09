"""Fusion 真实模型路径的 Plan → Compact DSL 两阶段编排回归。"""

import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.artifact_store import ArtifactStore
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    get_dsl_processor,
)
from services.widget_generation_service import WidgetGenerationService


@pytest.mark.asyncio
async def test_real_compact_route_runs_plan_before_dsl_without_plan_fewshots(
    monkeypatch,
) -> None:
    settings = get_settings()
    calls: list[tuple[str, list[dict[str, str]]]] = []
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)

    async def generate(
        _client,
        prompt,
        profile=None,
        **_kwargs,
    ) -> str:
        model_format = str((profile or {}).get("format"))
        calls.append((model_format, prompt))
        if model_format == "raw-json":
            return json.dumps(
                {
                    "name": "submit_card_plan",
                    "arguments": {
                        "info_required": [
                            {
                                "requirement": "卡片标题",
                                "text": "静态卡片",
                                "componentHints": ["Text"],
                            }
                        ],
                        "layoutHints": ["S-center"],
                    },
                },
                ensure_ascii=False,
            )
        return "source-compact-dsl"

    def process(source_dsl, context):
        assert context.compact_plan is not None
        assert context.compact_plan["info_required"][0]["text"] == "静态卡片"
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl='{"createSurface":{"surfaceId":"surface_card"}}',
        )

    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(processor, "process", process)
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: SimpleNamespace(
            artifactUrl="https://artifact.test/compact-plan",
            artifactDigest="sha256:compact-plan",
        ),
    )

    request = GenerateWidgetCardRequest(
        uid="test-user",
        prdVer="11.7.7.331",
        device={"romVersion": "7.0"},
        userQuery="生成一个名为静态卡片的卡片",
        size="2x2",
        title="静态卡片",
        description="两阶段生成测试",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        request
    )

    assert response.status == GenerationStatus.SUCCESS
    assert [item[0] for item in calls] == ["raw-json", "compact-dsl"]
    plan_system = calls[0][1][0]["content"]
    assert "submit_card_plan" in plan_system
    assert "# 2. Compact DSL 组件合同" in plan_system
    assert "### 7.1 `EventCard`" in plan_system
    assert "### `S-title-content-action`" in plan_system
    assert "FEWSHOT" not in plan_system
    dsl_system = calls[1][1][0]["content"]
    assert "已接受的 Compact Info Plan" in dsl_system
    assert '"layoutHints":["S-center"]' in dsl_system
