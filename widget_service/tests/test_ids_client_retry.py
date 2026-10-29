"""IDS 远程查询重试与 mock 隔离回归。"""

from unittest.mock import Mock

import pytest
import requests
from pydantic import ValidationError

from config.config import Settings
from models.generation import DeviceContext
from services.ids_client import IDSClient

_PAYLOAD = {
    "nameSpaces": [
        {
            "dataType": "t_ids_kv_ohos_installed_apps",
            "values": [{"data": {"bundleName": "com.example.weather"}}],
        }
    ]
}


def _response(status=200, content=None):
    response = requests.Response()
    response.status_code = status
    response._content = content if content is not None else b'{"nameSpaces": []}'
    return response


@pytest.fixture
def ids_client(monkeypatch, tmp_path):
    client = IDSClient(mock_response_path=tmp_path / "missing.json")
    monkeypatch.setattr(client.settings, "enable_ids_mock", False)
    monkeypatch.setattr(client.settings, "ids_query_url", "http://ids.local/query")
    monkeypatch.setattr(client.settings, "ids_request_retry_count", 1)
    monkeypatch.setattr(client, "build_ids_sign", Mock(side_effect=["sign1", "sign2", "sign3"]))
    monkeypatch.setattr("services.ids_client.time.sleep", Mock())
    return client


def _query(client):
    return client.get_device_capability_state(
        DeviceContext(romVersion="7.0", odid="test-odid"), "ids-retry-request"
    )


@pytest.mark.parametrize("retry_count", [0, 1, 2])
def test_retry_count_is_extra_attempts(ids_client, monkeypatch, retry_count):
    monkeypatch.setattr(ids_client.settings, "ids_request_retry_count", retry_count)
    request = Mock(side_effect=requests.Timeout("timeout"))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    log = Mock()
    monkeypatch.setattr("services.ids_client.logger", log)

    assert _query(ids_client).installed_apps == set()
    assert request.call_count == retry_count + 1
    assert ids_client.build_ids_sign.call_count == retry_count + 1
    assert "reason=exhausted" in str(log.warning.call_args)


@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("timeout"),
        requests.ConnectionError("connection"),
        _response(408),
        _response(429),
        _response(500),
        _response(503),
        _response(content=b"not json"),
        _response(content=b"[]"),
        _response(content=b"null"),
    ],
)
def test_retry_recovers_and_preserves_query(ids_client, monkeypatch, failure):
    success = Mock(status_code=200, content=b"payload")
    success.json.return_value = _PAYLOAD
    request = Mock(side_effect=[failure, success])
    monkeypatch.setattr("services.ids_client.requests.request", request)
    log = Mock()
    monkeypatch.setattr("services.ids_client.logger", log)

    assert _query(ids_client).installed_apps == {"com.example.weather"}
    assert request.call_count == 2
    first, second = request.call_args_list
    assert first.kwargs.get("json") == second.kwargs.get("json")
    body = second.kwargs.get("json")
    assert body is not None
    assert body.get("requestId") == "ids-retry-request"
    first_headers = first.kwargs.get("headers")
    second_headers = second.kwargs.get("headers")
    assert first_headers is not None
    assert second_headers is not None
    assert first_headers.get("idsSign") == "sign1"
    assert second_headers.get("idsSign") == "sign2"
    assert second.kwargs.get("timeout") == ids_client.settings.ids_request_timeout_seconds
    assert "ids_remote_query_recovered" in str(log.info.call_args_list)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_permanent_http_error_does_not_retry(ids_client, monkeypatch, status):
    request = Mock(return_value=_response(status))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    assert request.call_count == 1


def test_invalid_url_does_not_retry(ids_client, monkeypatch):
    request = Mock(side_effect=requests.exceptions.InvalidURL("bad url"))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    assert request.call_count == 1


def test_success_does_not_retry(ids_client, monkeypatch):
    request = Mock(return_value=_response())
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    assert request.call_count == 1


def test_mock_failure_does_not_query_remote(ids_client, monkeypatch):
    monkeypatch.setattr(ids_client.settings, "enable_ids_mock", True)
    request = Mock()
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    request.assert_not_called()
    ids_client.build_ids_sign.assert_not_called()


def test_placeholder_url_does_not_query_remote(ids_client, monkeypatch):
    monkeypatch.setattr(ids_client.settings, "ids_query_url", "http://{{ip}}/query")
    request = Mock()
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    request.assert_not_called()


@pytest.mark.parametrize("value", [-1, True, False, 1.0, 1.5, "-1", "bad", "1.5"])
def test_invalid_retry_configuration(value):
    with pytest.raises(ValidationError, match="ids_request_retry_count"):
        Settings(ids_request_retry_count=value)


@pytest.mark.parametrize("value,expected", [(0, 0), (2, 2), ("3", 3)])
def test_valid_retry_configuration(value, expected):
    assert Settings(ids_request_retry_count=value).ids_request_retry_count == expected


def test_retry_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_IDS_REQUEST_RETRY_COUNT", "4")
    assert Settings().ids_request_retry_count == 4
