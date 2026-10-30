"""能力概述 IDS 请求 ID 复用 router 的关联上下文。"""

from unittest.mock import Mock

import pytest
import requests

from api.routes import _request_id_from_raw_payload
from api.schemas import CapabilityOverviewRequest
from app.logger import session_id_context
from config.config import get_settings
from models.generation import DeviceContext
from services.ids_client import IDSClient
from services.widget_generation_service import WidgetGenerationService


@pytest.fixture
def remote_ids(monkeypatch, ids_retry_clock):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_ids_mock", False)
    monkeypatch.setattr(settings, "ids_query_url", "http://ids.local/query")
    monkeypatch.setattr(settings, "ids_installation_filter_package_names", (
        "com.huawei.hmsapp.totemweather", "com.huawei.hmos.health", "com.huawei.hmos.calendar",
    ))
    monkeypatch.setattr(settings, "ids_request_retry_budget_seconds", 10.0)
    monkeypatch.setattr(IDSClient, "build_ids_sign", lambda *_args, **_kwargs: "test-sign")
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"nameSpaces": []}'
    request = Mock(return_value=response)
    monkeypatch.setattr("services.ids_client.requests.request", request)
    return request


def _overview(router_request_id):
    token = session_id_context.set(router_request_id)
    try:
        WidgetGenerationService().get_widget_capability_overview(
            CapabilityOverviewRequest(uid="test-user", device=DeviceContext(romVersion="7.0"))
        )
    finally:
        session_id_context.reset(token)


@pytest.mark.parametrize("payload,expected", [
    ({"session": {"sessionId": "session123", "interactionId": "2"}}, "session123&2"),
    ({"requestId": "router-request"}, "router-request"),
])
def test_router_request_id_is_used_in_ids_body(remote_ids, payload, expected):
    router_request_id = _request_id_from_raw_payload(payload)
    assert router_request_id == expected
    _overview(router_request_id)
    remote_ids.assert_called_once()
    body = remote_ids.call_args.kwargs.get("json")
    assert isinstance(body, dict)
    assert body.get("requestId") == f"capability-overview&{expected}"


def test_each_round_has_own_ids_request_id(remote_ids):
    _overview("session123&1")
    _overview("session123&2")
    ids = []
    for invocation in remote_ids.call_args_list:
        body = invocation.kwargs.get("json")
        assert isinstance(body, dict)
        ids.append(body.get("requestId"))
    assert ids == [
        "capability-overview&session123&1",
        "capability-overview&session123&2",
    ]


@pytest.mark.parametrize("context_value", [None, "None", ""])
def test_direct_calls_without_router_use_unique_suffix(remote_ids, context_value):
    _overview(context_value)
    _overview(context_value)
    ids = set()
    for invocation in remote_ids.call_args_list:
        body = invocation.kwargs.get("json")
        assert isinstance(body, dict)
        request_id = body.get("requestId")
        assert isinstance(request_id, str)
        suffix = request_id.removeprefix("capability-overview&")
        assert len(suffix) == 32
        int(suffix, 16)
        ids.add(request_id)
    assert len(ids) == 2


def test_retry_keeps_prefixed_router_request_id(remote_ids):
    remote_ids.side_effect = [requests.Timeout("timeout"), remote_ids.return_value]
    _overview("session123&2")
    assert remote_ids.call_count == 2
    for invocation in remote_ids.call_args_list:
        body = invocation.kwargs.get("json")
        assert isinstance(body, dict)
        assert body.get("requestId") == "capability-overview&session123&2"
