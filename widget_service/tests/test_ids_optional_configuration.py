"""Unused IDS configuration must not block generation or the explicit mock path."""

from unittest.mock import Mock

import pytest

from config.config import Settings, get_settings
from models.generation import DeviceContext
from services.ids_client import IDSClient, IDSDeviceCapabilityState


def test_settings_accept_missing_ids_configuration():
    settings = Settings(ids_flow_control_id=None)
    assert settings.ids_flow_control_id is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_remote_requires_configuration_before_signing_or_http(monkeypatch, value):
    monkeypatch.setattr(get_settings(), "ids_flow_control_id", value)
    monkeypatch.setattr(get_settings(), "enable_ids_mock", False)
    client = IDSClient()
    sign = Mock(side_effect=AssertionError("must not sign"))
    http = Mock(side_effect=AssertionError("must not request"))
    monkeypatch.setattr(client, "build_ids_sign", sign)
    monkeypatch.setattr(client, "_query_remote_ids", http)
    with pytest.raises(ValueError, match="ids_flow_control_id"):
        client.get_device_capability_state(DeviceContext(romVersion="7.0"), "test")
    sign.assert_not_called()
    http.assert_not_called()


def test_explicit_mock_needs_no_remote_configuration(monkeypatch):
    monkeypatch.setattr(get_settings(), "ids_flow_control_id", None)
    monkeypatch.setattr(get_settings(), "enable_ids_mock", True)
    client = IDSClient()
    state = IDSDeviceCapabilityState(installed_apps={"test.package"})
    monkeypatch.setattr(client, "_load_mock_state", lambda _request_id: state)
    remote = Mock(side_effect=AssertionError("must not construct remote query"))
    monkeypatch.setattr(client, "build_installed_apps_query", remote)
    assert client.get_device_capability_state(DeviceContext(romVersion="7.0"), "test") is state
    remote.assert_not_called()


def test_configured_value_passed_unchanged(monkeypatch):
    monkeypatch.setattr(get_settings(), "ids_flow_control_id", "test-flow")
    client = IDSClient()
    monkeypatch.setattr(client, "build_ids_sign", lambda *_args, **_kwargs: "test-sign")
    result = client.build_installed_apps_query(DeviceContext(romVersion="7.0"), "test")
    assert result.headers.model_dump(by_alias=True).get("devFakeId") == "test-flow"
