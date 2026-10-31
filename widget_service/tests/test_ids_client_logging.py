"""IDS 普通日志诊断；不依赖 Trace，不改变查询业务结果。"""

import json
from unittest.mock import Mock

import pytest
import requests

from models.generation import DeviceContext
from services.ids_client import IDSClient
from services.ids_response_logging import ids_response_diagnostic

_NAMESPACE = "t_ids_kv_ohos_installed_apps"


@pytest.fixture
def client_and_log(monkeypatch, ids_retry_clock):
    client = IDSClient()
    monkeypatch.setattr(client.settings, "enable_ids_mock", False)
    monkeypatch.setattr(client.settings, "enable_sensitive_log_fields", False)
    monkeypatch.setattr(client.settings, "ids_query_url", "http://ids.local/query")
    monkeypatch.setattr(client.settings, "ids_request_retry_budget_seconds", 0.0)
    monkeypatch.setattr(client, "build_ids_sign", lambda **_kwargs: "private-sign")
    log = Mock()
    monkeypatch.setattr("services.ids_client.logger", log)
    return client, log


def _query(client):
    return client.get_device_capability_state(
        DeviceContext(romVersion="7.0", odid="private-odid"), "ids-log-request"
    )


def _respond(monkeypatch, payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Mock(return_value=response)
    monkeypatch.setattr("services.ids_client.requests.request", request)
    return request


def _diagnostic(log):
    for invocation in log.info.call_args_list:
        message = invocation.args[0]
        if "ids_remote_response_diagnostic" in message:
            assert "request_id=ids-log-request" in message
            assert "attempt=1" in message
            assert "\n" not in message
            return json.loads(message.split("diagnostic=", 1)[1])
    pytest.fail("missing INFO response diagnostic")


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"retCode": 403, "description": "查询无权限"}, "namespaces_missing"),
        ({"nameSpaces": []}, "namespaces_empty"),
        ({"nameSpaces": None}, "namespaces_not_list"),
        ({"nameSpaces": {}}, "namespaces_not_list"),
        ({"nameSpaces": [{"dataType": "other"}]}, "installed_namespace_missing"),
        ([], "payload_not_object"),
    ],
)
def test_response_shape_diagnostics(payload, reason):
    assert ids_response_diagnostic(payload).get("reason") == reason


def test_business_error_and_empty_namespace_are_visible(client_and_log, monkeypatch):
    client, log = client_and_log
    payload = {
        "retCode": 0, "description": "OK",
        "nameSpaces": [{
            "retCode": 901, "description": "设备暂无记录",
            "dataType": _NAMESPACE, "values": [],
        }],
    }
    request = _respond(monkeypatch, payload)
    assert _query(client).installed_apps == set()
    request.assert_called_once()
    diagnostic = _diagnostic(log)
    assert diagnostic.get("status") == {"retCode": 0, "description": "OK"}
    namespaces = diagnostic.get("namespaces")
    assert isinstance(namespaces, list)
    assert namespaces[0].get("status") == {"retCode": 901, "description": "设备暂无记录"}
    assert namespaces[0].get("valuesCount") == 0
    assert "installation_state=unknown" in str(log.warning.call_args_list)


def test_success_logs_counts_without_full_installation_data(client_and_log, monkeypatch):
    client, log = client_and_log
    _respond(monkeypatch, {"nameSpaces": [{
        "dataType": _NAMESPACE,
        "values": [{"data": {"bundleName": "com.example.private", "appName": "私有应用"}}],
    }]})
    assert _query(client).installed_apps == {"com.example.private"}
    namespaces = _diagnostic(log).get("namespaces")
    assert isinstance(namespaces, list)
    assert namespaces[0].get("bundleRecordCount") == 1
    assert "私有应用" not in str(log.mock_calls)
    assert "com.example.private" not in str(log.mock_calls)
    assert "ids_no_installed_app_records" not in str(log.mock_calls)


def test_malformed_records_are_visible(client_and_log, monkeypatch):
    client, log = client_and_log
    _respond(monkeypatch, {"nameSpaces": [{
        "dataType": _NAMESPACE, "values": [{"data": {}}, {"data": None}],
    }]})
    with pytest.raises(AttributeError):
        _query(client)
    namespaces = _diagnostic(log).get("namespaces")
    assert isinstance(namespaces, list)
    assert namespaces[0].get("missingOrInvalidBundleRecordCount") == 2
    assert "ids_payload_parse_failed" in str(log.error.call_args_list)


def test_http_error_body_is_diagnosed_without_new_retry(client_and_log, monkeypatch):
    client, log = client_and_log
    request = _respond(monkeypatch, {"retCode": "DENIED", "description": "鉴权失败"}, 403)
    assert _query(client).installed_apps == set()
    request.assert_called_once()
    assert _diagnostic(log).get("status") == {"retCode": "DENIED", "description": "鉴权失败"}


def test_response_echo_is_redacted_and_single_line(client_and_log, monkeypatch):
    client, log = client_and_log
    _respond(monkeypatch, {"description": "private-odid\nprivate-sign", "nameSpaces": []})
    _query(client)
    diagnostic = _diagnostic(log)
    assert "private-odid" not in json.dumps(diagnostic)
    assert "private-sign" not in json.dumps(diagnostic)
    assert "[REDACTED]" in json.dumps(diagnostic)


def test_retry_error_log_is_warning_and_single_line(client_and_log, monkeypatch):
    client, log = client_and_log
    monkeypatch.setattr(client.settings, "ids_request_retry_budget_seconds", 10.0)
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"nameSpaces": []}'
    request = Mock(side_effect=[requests.Timeout("failed\nprivate-odid"), response])
    monkeypatch.setattr("services.ids_client.requests.request", request)
    _query(client)
    log.error.assert_not_called()
    messages = [invocation.args[0] for invocation in log.warning.call_args_list]
    for message in messages:
        assert "\n" not in message
        assert "private-odid" not in message
    assert "will_retry=True" in str(messages)
    assert "ids_remote_query_recovered" in str(log.info.call_args_list)


def test_invalid_json_body_is_not_logged(client_and_log, monkeypatch):
    client, log = client_and_log
    response = requests.Response()
    response.status_code = 502
    response._content = b"<html>private-odid secret-upstream-content</html>"
    monkeypatch.setattr("services.ids_client.requests.request", Mock(return_value=response))
    assert _query(client).installed_apps == set()
    messages = str(log.mock_calls)
    assert "reason=invalid_json body_omitted=true" in messages
    assert "secret-upstream-content" not in messages
    assert "private-odid" not in messages


def test_refreshed_signature_is_redacted(client_and_log):
    client, _log = client_and_log
    query = client.build_installed_apps_query(DeviceContext(romVersion="7.0"), "request")
    text = client._response_log_text(
        {"description": "refreshed-sign"}, query, {"idsSign": "refreshed-sign"}
    )
    assert "refreshed-sign" not in text
    assert "[REDACTED]" in text


def test_summary_is_bounded():
    summary = ids_response_diagnostic({
        "description": "长" * 600,
        "nameSpaces": [{"dataType": _NAMESPACE, "values": []}] * 21,
    })
    status = summary.get("status")
    assert isinstance(status, dict)
    assert status.get("descriptionTruncated") is True
    assert len(status.get("description")) == 512
    namespaces = summary.get("namespaces")
    assert isinstance(namespaces, list)
    assert len(namespaces) == 20
    assert summary.get("namespacesTruncated") is True
    assert summary.get("installedNamespaceCount") == 21
