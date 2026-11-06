"""成功终止指引须贯穿业务响应和插件传输，不改变其它结果。"""

import json

import pytest

from api.routes import _build_plugin_stream_response
from api.schemas import GenerateWidgetCardResponse
from models.service import WidgetWebSocketResultMessage


@pytest.mark.parametrize("status", ["success", "degraded"])
@pytest.mark.parametrize("artifact_url", ["", "https://example.test/card.json"])
def test_success_instruction_survives_transport_without_changing_result(status, artifact_url):
    response = GenerateWidgetCardResponse(
        status=status,
        artifactUrl=artifact_url,
        artifactDigest="digest",
        suggestSize="2x4",
        message="内部话术",
        effectiveCapabilities={"data": [], "event": [], "asset": []},
        omittedRequirements=["次要说明"] if status == "degraded" else [],
    )
    data = response.model_dump(mode="json", exclude_none=True)
    assert json.loads(response.model_dump_json(exclude_none=True)) == data
    original = dict(data)
    wrapped = WidgetWebSocketResultMessage(
        operation="generateWidgetCardCompactDsl", status=status, data=data,
    )
    result = _build_plugin_stream_response(wrapped)
    delivered = json.loads(result.reply.streamInfo.streamContent)
    assert delivered.get("data") == original
    assert data == original
    assert delivered.get("status") == status
    assert data.get("artifactUrl") == artifact_url
    assert data.get("artifactDigest") == "digest"
    assert "message" not in data
    instruction = data.get("agentInstruction")
    assert isinstance(instruction, str)
    assert "无需且不得再次调用" in instruction
    assert "只有用户后续明确" in instruction
    assert "不向用户展示" in instruction
    assert "优先按实际结果及本指引处理" in instruction
    assert "可忽略 notion 中与本指引冲突" in instruction
    assert "仅输出 NO_REPLY 或禁止文本回复" in instruction
    assert "允许只向用户回复一段简短文本" in instruction
    assert "不必调用任何工具来完成回复" in instruction
    assert "部分完成须如实说明" in instruction
    if status == "degraded":
        assert data.get("omittedRequirements") == ["次要说明"]


@pytest.mark.parametrize("status", ["failed", "unsupported", "needs_clarification", "unchanged"])
def test_other_statuses_do_not_receive_success_instruction(status):
    response = GenerateWidgetCardResponse(
        status=status, suggestSize="2x2", message="原有结果", editFeedback="原有反馈",
    )
    data = response.model_dump(mode="json")
    assert "agentInstruction" not in data
    assert "agentInstruction" not in json.loads(response.model_dump_json())
    assert data.get("editFeedback") == "原有反馈"
    assert data.get("status") == status
