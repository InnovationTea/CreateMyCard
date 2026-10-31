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
def ids_client(monkeypatch, tmp_path, ids_retry_clock):
    client = IDSClient(mock_response_path=tmp_path / "missing.json")
    monkeypatch.setattr(client.settings, "enable_ids_mock", False)
    monkeypatch.setattr(client.settings, "ids_query_url", "http://ids.local/query")
    monkeypatch.setattr(client.settings, "ids_request_retry_budget_seconds", 10.0)
    monkeypatch.setattr(client.settings, "ids_request_retry_initial_delay_seconds", 0.5)
    monkeypatch.setattr(client.settings, "ids_request_retry_backoff_multiplier", 2.0)
    signatures = [f"sign{number}" for number in range(1, 100)]
    monkeypatch.setattr(client, "build_ids_sign", Mock(side_effect=signatures))
    return client


def _query(client):
    return client.get_device_capability_state(
        DeviceContext(romVersion="7.0", odid="test-odid"), "ids-retry-request"
    )


@pytest.mark.parametrize("budget,attempts", [(0.0, 1), (0.5, 1), (1.0, 2), (10.0, 5)])
def test_time_window_limits_attempts(ids_client, monkeypatch, budget, attempts):
    monkeypatch.setattr(ids_client.settings, "ids_request_retry_budget_seconds", budget)
    request = Mock(side_effect=requests.Timeout("timeout"))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    log = Mock()
    monkeypatch.setattr("services.ids_client.logger", log)

    assert _query(ids_client).installed_apps == set()
    assert request.call_count == attempts
    assert ids_client.build_ids_sign.call_count == attempts
    assert "budget" in str(log.warning.call_args_list)


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


@pytest.mark.parametrize("name", [
    "ids_request_retry_budget_seconds",
    "ids_request_retry_initial_delay_seconds",
    "ids_request_retry_backoff_multiplier",
])
@pytest.mark.parametrize("value", [-1, True, False, "bad", "nan", "inf", "-inf"])
def test_invalid_retry_configuration(name, value):
    with pytest.raises(ValidationError, match=name):
        Settings(**{name: value})


@pytest.mark.parametrize("value,expected", [(0, 0.0), (2.5, 2.5), ("3.5", 3.5)])
def test_valid_retry_configuration(value, expected):
    settings = Settings(ids_request_retry_budget_seconds=value)
    assert settings.ids_request_retry_budget_seconds == expected


def test_retry_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_IDS_REQUEST_RETRY_BUDGET_SECONDS", "4")
    monkeypatch.setenv("WIDGET_SERVICE_IDS_REQUEST_RETRY_INITIAL_DELAY_SECONDS", "0.25")
    monkeypatch.setenv("WIDGET_SERVICE_IDS_REQUEST_RETRY_BACKOFF_MULTIPLIER", "3")
    settings = Settings()
    assert settings.ids_request_retry_budget_seconds == 4.0
    assert settings.ids_request_retry_initial_delay_seconds == 0.25
    assert settings.ids_request_retry_backoff_multiplier == 3.0


@pytest.mark.parametrize("name,value", [
    ("ids_request_retry_initial_delay_seconds", 0),
    ("ids_request_retry_backoff_multiplier", 0),
    ("ids_request_retry_backoff_multiplier", 1),
])
def test_non_increasing_backoff_is_rejected(name, value):
    with pytest.raises(ValidationError, match=name):
        Settings(**{name: value})


@pytest.mark.parametrize("initial,multiplier,expected", [
    (0.5, 2.0, [0.5, 1.0, 2.0, 4.0]),
    (1.0, 3.0, [1.0, 3.0]),
])
def test_exponential_delays(
    ids_client, ids_retry_clock, monkeypatch, initial, multiplier, expected
):
    monkeypatch.setattr(ids_client.settings, "ids_request_retry_initial_delay_seconds", initial)
    monkeypatch.setattr(ids_client.settings, "ids_request_retry_backoff_multiplier", multiplier)
    request = Mock(side_effect=requests.Timeout("timeout"))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    assert ids_retry_clock.sleeps == expected
    assert request.call_count == len(expected) + 1


@pytest.mark.parametrize("succeed", [False, True])
def test_inflight_last_request_can_finish_after_deadline(
    ids_client, ids_retry_clock, monkeypatch, succeed
):
    attempts = []

    def send(**_kwargs):
        attempts.append(ids_retry_clock.now)
        if len(attempts) == 1:
            ids_retry_clock.now += 8.0
            raise requests.Timeout("first request failed")
        ids_retry_clock.now += 3.0
        if not succeed:
            raise requests.Timeout("last request failed")
        return _response(content=(
            b'{"nameSpaces":[{"dataType":"t_ids_kv_ohos_installed_apps",'
            b'"values":[{"data":{"bundleName":"app"}}]}]}'
        ))

    monkeypatch.setattr("services.ids_client.requests.request", send)
    state = _query(ids_client)
    assert attempts == [0.0, 8.5]
    assert ids_retry_clock.now == 11.5
    assert state.installed_apps == ({"app"} if succeed else set())
    assert ids_retry_clock.sleeps == [0.5]


def test_request_time_consumes_budget(ids_client, ids_retry_clock, monkeypatch):
    def send(**_kwargs):
        ids_retry_clock.now += 10.0
        raise requests.Timeout("deadline reached")

    request = Mock(side_effect=send)
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    request.assert_called_once()
    assert ids_retry_clock.sleeps == []


@pytest.mark.parametrize("overrun_stage", ["sleep", "sign"])
def test_no_request_after_sleep_or_signature_exhausts_window(
    ids_client, ids_retry_clock, monkeypatch, overrun_stage
):
    def overrun(*_args, **_kwargs):
        ids_retry_clock.now = 10.0
        return "sign"

    if overrun_stage == "sleep":
        monkeypatch.setattr("services.ids_client.time.sleep", overrun)
    else:
        monkeypatch.setattr(ids_client, "build_ids_sign", Mock(side_effect=["first", "second"]))
        original_sign = ids_client.build_ids_sign

        def sign(**kwargs):
            if not kwargs:
                return overrun()
            return original_sign(**kwargs)

        monkeypatch.setattr(ids_client, "build_ids_sign", sign)
    request = Mock(side_effect=requests.Timeout("timeout"))
    monkeypatch.setattr("services.ids_client.requests.request", request)
    assert _query(ids_client).installed_apps == set()
    request.assert_called_once()
