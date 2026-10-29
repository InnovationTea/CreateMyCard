"""必要动态输入缺口的合同、编排、对外指引及静态边界回归；不调用真实模型。"""

import copy
import json

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode
from custom.a2ui_model_client import A2UIModelClient
from services.artifact_store import ArtifactStore
from services.compact_dsl_interface_retry import run_compact_dsl_with_retry
from services.generation_input_feedback import (
    MissingDataInputError,
    MissingDataReportValidationError,
    missing_data_tool,
    parse_missing_data_report,
)
from services.widget_generation_service import WidgetGenerationService

QUERY = "做一张卡片显示手机当前电量与充电状态"
QUOTE = "手机当前电量与充电状态"


def _report():
    return {
        "name": "report_missing_data",
        "arguments": {"requirements": [{
            "description": "需要读取手机当前电量与充电状态", "sourceQuote": QUOTE,
        }]},
    }


def _parse(payload, *, allow=True):
    return parse_missing_data_report(
        json.dumps(payload, ensure_ascii=False), QUERY, allow_report=allow,
    )


def test_report_contains_diagnostics_but_no_capability_or_permission_authorization():
    report = _parse(_report())
    assert report is not None
    details = MissingDataInputError(report).details()
    assert details.get("stage") == "generationInput"
    assert details.get("modelCalled") is True
    assert details.get("retryable") is True
    assert details.get("requiredActions") == ["REFRESH_CAPABILITIES", "FIX_AND_RETRY"]
    issues = details.get("issues")
    assert isinstance(issues, list)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.get("path") == "/candidateDataBindings"
    assert issue.get("capabilityId") == ""
    assert issue.get("code") == "REQUIRED_DATA_INPUT_MISSING"
    assert "sourceQuote" not in json.dumps(details)
    assert "三次总调用预算" in details.get("agentInstruction", "")
    assert "权限" in issue.get("repairInstruction", "")


@pytest.mark.parametrize("bad", [
    {"requirements": []},
    {"requirements": [{"description": "", "sourceQuote": QUOTE}]},
    {"requirements": [{"description": "缺数据", "sourceQuote": "用户没有说过的内容"}]},
    {"requirements": [{"description": "缺数据", "sourceQuote": QUOTE, "capabilityId": "fake"}]},
    {
        "requirements": [{"description": "缺数据", "sourceQuote": QUOTE}],
        "candidateDataBindings": [],
    },
    {"requirements": [{"description": "缺数据", "sourceQuote": QUOTE}] * 9},
    "not-an-object",
])
def test_invalid_report_does_not_authorize_input_retry(bad):
    with pytest.raises(MissingDataReportValidationError):
        _parse({"name": "report_missing_data", "arguments": bad})


def test_report_cannot_be_mixed_with_normal_plan_or_used_for_edit():
    with pytest.raises(MissingDataReportValidationError):
        _parse({**_report(), "info_required": []})
    with pytest.raises(MissingDataReportValidationError, match="编辑"):
        _parse(_report(), allow=False)


@pytest.mark.parametrize("raw", [
    "not json", '{"name":"report_missing_data","arguments":',
    '{"name":"submit_card_plan","name":"report_missing_data","arguments":{}}',
    '{"name":"submit_card_plan","arguments":{"info_required":[]}}',
])
def test_other_or_ambiguous_output_remains_with_original_plan_validator(raw):
    assert parse_missing_data_report(raw, QUERY, allow_report=True) is None


def test_tool_contract_exposes_no_fields_for_model_to_add_data_bindings():
    tool = missing_data_tool()
    parameters = tool.get("parameters")
    assert isinstance(parameters, dict)
    assert parameters.get("additionalProperties") is False
    assert parameters.get("required") == ["requirements"]
    assert set(parameters.get("properties", {})) == {"requirements"}


def _request(*, mixed=False):
    bindings = []
    if mixed:
        bindings.append({
            "capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "/data/weather",
            "candidateOutputFields": ["/current/temperatureText"],
        })
    return GenerateWidgetCardRequest(
        uid="test-input-feedback", prdVer="11.7.7.330", device={"romVersion": "7.0"},
        userQuery=QUERY, size="2x2", title="状态", description="状态速览",
        candidateDataBindings=bindings,
    )


def _configure(monkeypatch, callback):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_card_template", False)
    monkeypatch.setattr(settings, "enable_widget_directive_commands", False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: False)
    monkeypatch.setattr(A2UIModelClient, "generate", callback)

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("missing dynamic inputs must not save an artifact")

    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True])
async def test_missing_data_stops_before_dsl_and_does_not_retry_same_inputs(monkeypatch, mixed):
    calls = []

    async def generate(_self, prompt, profile=None, **_kwargs):
        calls.append(copy.deepcopy(profile))
        assert (profile or {}).get("id") == "compact-info-plan"
        context = "\n".join(message.get("content", "") for message in prompt)
        assert "report_missing_data" in context
        return json.dumps(_report(), ensure_ascii=False)

    _configure(monkeypatch, generate)
    request = _request(mixed=mixed)
    before = request.model_dump(mode="json")
    service = WidgetGenerationService()
    with pytest.raises(MissingDataInputError):
        await run_compact_dsl_with_retry(
            service.generate_widget_card_compact_dsl, request,
            enabled=True, retry_count=3, request_id="input-feedback",
        )
    assert len(calls) == 1
    assert request.model_dump(mode="json") == before


@pytest.mark.asyncio
@pytest.mark.parametrize("old_plan_error", [False, True])
async def test_invalid_report_consumes_plan_budget_without_input_retry_authorization(
    monkeypatch, old_plan_error,
):
    calls = []

    async def generate(_self, _prompt, profile=None, **_kwargs):
        calls.append(profile)
        wrong = _report()
        wrong["arguments"] = {"requirements": []}
        if old_plan_error:
            wrong = {"name": "submit_card_plan", "arguments": {"info_required": [{
                "requirement": "展示手机电量", "priority": "must",
            }]}}
        return json.dumps(wrong)

    _configure(monkeypatch, generate)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.A2UI_GENERATION_FAILED.value
    assert len(calls) == 2
    assert not response.artifactUrl


@pytest.mark.parametrize("action_only", [False, True])
def test_empty_data_accepts_static_and_action_plans_without_missing_input_error(action_only):
    from services.compact_plan import parse_compact_plan_call
    from services.generation_content_policy import (
        content_policy_scope,
        resolve_content_policy,
    )

    query = "写上每天开心" if not action_only else "点按打开电池设置"
    fact = {
        "requirement": "展示固定文字", "priority": "must", "text": "每天开心",
        "sourceTexts": ["每天开心"], "componentHints": ["EmphasisText"],
    }
    events = []
    groups = [{"id": "greeting", "kind": "object", "identity": None, "factIndexes": [0]}]
    layouts = ["S-static-content"]
    if action_only:
        fact = {
            "requirement": "打开电池设置", "priority": "must",
            "actionId": "event.open.settings.battery", "componentHints": ["CardButton"],
        }
        events = [{"id": "event.open.settings.battery", "call": "clickToDeeplink", "args": {}}]
        groups = []
        layouts = ["S-title-content-action"]
    arguments = {"info_required": [fact], "layoutHints": layouts}
    if not action_only:
        arguments["contentGroups"] = groups
    raw = json.dumps({"name": "submit_card_plan", "arguments": arguments}, ensure_ascii=False)
    task = {
        "userQuery": query, "size": "2x2", "dataModelSchema": {"data": {}},
        "eventCandidates": events, "assetCandidates": [],
    }
    policy = resolve_content_policy(
        operation="generateWidgetCardCompactDsl", enabled=True, is_edit=False,
        requested_data=False, effective_data=False,
        requested_events=action_only, effective_events=action_only,
    )
    assert policy.is_static == (not action_only)
    with content_policy_scope(policy):
        assert parse_missing_data_report(raw, query, allow_report=True) is None
        accepted = parse_compact_plan_call(raw, task)
    facts = accepted.plan.get("info_required")
    assert isinstance(facts, list)
    assert len(facts) == 1
    assert not facts[0].get("dataId")
    if action_only:
        assert facts[0].get("actionId") == "event.open.settings.battery"
    else:
        assert facts[0].get("text") == "每天开心"


def test_websocket_final_exposes_structured_input_guidance(monkeypatch):
    from fastapi.testclient import TestClient

    from test_tool_dispatch_routes import (
        _receive_frames_until_final,
        _request_id,
        _tool_payload,
        app,
    )
    from ws_response_parser import parse_legacy_stream_content

    calls = []

    async def generate(_self, _prompt, profile=None, **_kwargs):
        calls.append(profile)
        return json.dumps(_report(), ensure_ascii=False)

    _configure(monkeypatch, generate)
    monkeypatch.setattr(get_settings(), "enable_compact_dsl_interface_retry", True)
    monkeypatch.setattr(get_settings(), "compact_dsl_interface_retry_count", 2)
    content = {"userQuery": QUERY, "title": "电池", "description": "电池信息", "size": "2x2"}
    request_id = _request_id("missing-input")
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl",
    ) as websocket:
        websocket.send_json(_tool_payload(content, "missing-input"))
        frames = _receive_frames_until_final(websocket, request_id)
    final = frames[-1]
    reply = final.get("reply")
    assert isinstance(reply, dict)
    stream = reply.get("streamInfo")
    assert isinstance(stream, dict)
    assert stream.get("streamType") == "final"
    message = parse_legacy_stream_content(stream.get("streamContent", ""))
    assert message.get("status") == "failed"
    assert message.get("errorCode") == ErrorCode.GENERATION_INPUT_INCOMPLETE.value
    error = message.get("error")
    assert isinstance(error, dict)
    details = error.get("details")
    assert isinstance(details, dict)
    assert details.get("retryable") is True
    assert details.get("modelCalled") is True
    assert details.get("stage") == "generationInput"
    assert "停止本轮调用" not in error.get("message", "")
    assert len(calls) == 1
