"""Fusion 真实模型路径的 Plan → Compact DSL 两阶段编排回归。"""

import copy
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

# 本组验证既有创建、回退或路由合同，静态策略由专项测试覆盖。
pytestmark = pytest.mark.usefixtures("existing_generation_policy")


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
@pytest.mark.parametrize("plan_format", ["plain", "dsml", "call", "invalid_then_json"])
async def test_real_compact_route_runs_plan_before_dsl_without_plan_fewshots(
    monkeypatch,
    plan_format: str,
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
        calls.append((model_format, copy.deepcopy(prompt)))
        if model_format == "raw-json":
            output = json.dumps(
                {
                    "name": "submit_card_plan",
                    "arguments": {
                        "info_required": [
                            {
                                "requirement": "卡片标题",
                                "priority": "must",
                                "text": "静态卡片",
                                "componentHints": ["EmphasisText"],
                            }
                        ],
                        "layoutHints": ["S-center"],
                    },
                },
                ensure_ascii=False,
            )
            if plan_format == "dsml":
                payload = json.loads(output)
                arguments = payload.get("arguments")
                assert isinstance(arguments, dict)
                return (
                    '<｜｜DSML｜｜ calls>\n<｜｜DSML｜｜ invoke name="submit_card_plan">\n'
                    '<｜｜DSML｜｜ parameter name="arguments" string="false">'
                    + json.dumps(arguments, ensure_ascii=False)
                    + '</｜｜DSML｜｜ parameter>\n</｜｜DSML｜｜ invoke>\n</｜｜DSML｜｜ calls>'
                )
            if plan_format == "call":
                return "call\n" + output
            if plan_format == "invalid_then_json" and len(calls) == 1:
                return '<｜｜DSML｜｜ calls>\n<｜｜DSML｜｜ invoke name="other_tool">{}'
            return output
        return (
            '["root","Layout",{"layout":"S-title-content"},["title","content"]]\n'
            '["title","SingleLineTitle",{"title":"概览","fontSize":12}]\n'
            '["content","EmphasisText",{"mainText":"静态卡片","fontSize":18}]'
        )

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
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
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
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status == GenerationStatus.SUCCESS
    expected_formats = ["raw-json", "compact-dsl"]
    if plan_format == "invalid_then_json":
        expected_formats.insert(0, "raw-json")
    assert [item[0] for item in calls] == expected_formats
    plan_system = calls[0][1][0]["content"]
    assert "submit_card_plan" in plan_system
    assert "你是 HarmonyOS 桌面卡片生成 Agent" in plan_system
    assert "`plan`：按本轮工具 Schema 提交一次" in plan_system
    assert "# 2. 单组件细则" in plan_system
    assert "先选定本轮真正展示的内容" in plan_system
    assert "不能因小卡、条数多或容量紧张而省略" in plan_system
    assert "不把它列为 actionId、不分配按钮素材、不计入必要动作数" in plan_system
    assert "`EventCard`" in plan_system
    assert "| S-title-content-action |" in plan_system
    assert "FEWSHOT" not in plan_system
    assert '"composition"' not in plan_system.split("# 可用工具合同", 1)[1]
    plan_messages = calls[0][1]
    dsl_messages = calls[-1][1]
    plan_context = "\n".join(message["content"] for message in plan_messages)
    assert "<agent_stage>plan</agent_stage>" in plan_context
    assert "这是文本 JSON 协议，不是原生工具调用" in plan_context
    if plan_format == "invalid_then_json":
        feedback_message = calls[1][1][-1].get("content")
        assert isinstance(feedback_message, str)
        feedback = json.loads(feedback_message)
        output_format = feedback.get("outputFormat")
        assert isinstance(output_format, dict)
        assert output_format.get("detectedEnvelope") == "DSML"
    assert dsl_messages[: len(plan_messages)] == plan_messages
    assert sum(message["role"] == "system" for message in dsl_messages) == 1
    assert any(message["role"] == "assistant" for message in dsl_messages)
    dsl_context = "\n".join(message["content"] for message in dsl_messages)
    assert "已接受的 Compact Info Plan" in dsl_context
    assert '"layoutHints":["S-center"]' in dsl_context
    assert "<agent_stage>compact_dsl</agent_stage>" in dsl_context


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
async def test_runtime_plan_mode_repairs_missing_composition_before_dsl(
    monkeypatch,
) -> None:
    settings = get_settings()
    calls: list[tuple[str, list[dict[str, str]]]] = []
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)

    async def generate(_client, _prompt, profile=None, **_kwargs) -> str:
        model_format = str((profile or {}).get("format"))
        calls.append((model_format, copy.deepcopy(_prompt)))
        if model_format != "raw-json":
            return (
                '["root","Layout",{"layout":"S-title-content"},["title","content"]]\n'
                '["title","SingleLineTitle",{"title":"概览","fontSize":12}]\n'
                '["content","EmphasisText",{"mainText":"静态卡片","fontSize":18}]'
            )
        arguments = {
            "info_required": [
                {
                    "requirement": "卡片标题",
                    "priority": "must",
                    "text": "静态卡片",
                    "componentHints": ["EmphasisText"],
                }
            ],
            "layoutHints": ["S-center"],
        }
        plan_call_count = sum(item[0] == "raw-json" for item in calls)
        if plan_call_count > 1:
            arguments["composition"] = {
                "layout": "S-center",
                "variant": 1,
                "regions": [
                    {
                        "id": "content",
                        "path": [],
                        "referenceWidth": 126,
                        "referenceHeight": 126,
                        "gap": 0,
                        "groups": [
                            {
                                "component": "EmphasisText",
                                "factIndexes": [0],
                                "placements": ["mainText"],
                                "referenceHeight": 30,
                            }
                        ],
                    }
                ],
            }
        return json.dumps(
            {"name": "submit_card_plan", "arguments": arguments},
            ensure_ascii=False,
        )

    def process(source_dsl, context):
        assert context.compact_plan is not None
        assert context.compact_plan["composition"]["layout"] == "S-center"
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl='{"createSurface":{"surfaceId":"surface_card"}}',
        )

    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", True)
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
            artifactUrl="https://artifact.test/compact-plan-runtime",
            artifactDigest="sha256:compact-plan-runtime",
        ),
    )
    request = GenerateWidgetCardRequest(
        uid="test-user",
        prdVer="11.7.7.331",
        device={"romVersion": "7.0"},
        userQuery="生成一个名为静态卡片的卡片",
        size="2x2",
        title="静态卡片",
        description="Plan 容量模式重试测试",
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status == GenerationStatus.SUCCESS
    assert [item[0] for item in calls] == ["raw-json", "raw-json", "compact-dsl"]
    repaired_plan_messages = calls[1][1]
    assert any(message["role"] == "assistant" for message in repaired_plan_messages)
    plan_feedback = json.loads(repaired_plan_messages[-1]["content"])
    assert plan_feedback["toolResult"]["name"] == "submit_card_plan"
    assert plan_feedback["toolResult"]["ok"] is False
