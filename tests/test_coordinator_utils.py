from types import SimpleNamespace

import pytest
import requests

from custom_components.huawei_charger.coordinator import (
    AuthenticationFailed,
    HuaweiChargerCoordinator,
    UpdateFailed,
)
from custom_components.huawei_charger.const import DEFAULT_LOCALE, DEFAULT_TIMEZONE_OFFSET


def build_coordinator(language="en-US", time_zone="UTC"):
    coordinator = object.__new__(HuaweiChargerCoordinator)
    coordinator.hass = SimpleNamespace(
        config=SimpleNamespace(language=language, time_zone=time_zone)
    )
    coordinator.entry = SimpleNamespace(data={}, options={})
    coordinator.verify_ssl = False
    coordinator.request_timeout = 15
    coordinator.token = None
    coordinator.headers = {}
    coordinator.region_ip = "1.2.3.4"
    coordinator.dn_id = "station"
    coordinator.wallbox_dn_id = "wallbox"
    coordinator.param_values = {}
    return coordinator


class FailingJsonResponse:
    def json(self):
        raise ValueError("bad json")


class DummyResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                response=SimpleNamespace(status_code=self.status_code)
            )


def test_derive_locale_variants():
    coordinator = build_coordinator(language="en-US")
    assert coordinator._derive_locale() == "en_US"

    coordinator.hass.config.language = "fr"
    assert coordinator._derive_locale() == DEFAULT_LOCALE

    coordinator.hass.config.language = None
    assert coordinator._derive_locale() == DEFAULT_LOCALE


def test_derive_timezone_offset_valid():
    coordinator = build_coordinator(time_zone="UTC")
    assert coordinator._derive_timezone_offset() == 0


def test_derive_timezone_offset_invalid():
    coordinator = build_coordinator(time_zone="Invalid/Zone")
    assert coordinator._derive_timezone_offset() == DEFAULT_TIMEZONE_OFFSET


def test_json_or_error_with_default(caplog):
    coordinator = build_coordinator()
    result = coordinator._json_or_error(FailingJsonResponse(), "context", default={})
    assert result == {}
    assert any("Response for context was not JSON" in message for message in caplog.messages)


def test_json_or_error_without_default():
    coordinator = build_coordinator()
    with pytest.raises(UpdateFailed):
        coordinator._json_or_error(FailingJsonResponse(), "context")


def test_request_post_success(monkeypatch):
    coordinator = build_coordinator()
    response = DummyResponse({"ok": True}, status_code=200)

    def fake_post(url, *, json=None, data=None, headers=None, verify=None, timeout=None):
        assert verify is coordinator.verify_ssl
        assert timeout == coordinator.request_timeout
        return response

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.post", fake_post
    )

    result = coordinator._request_post(
        "https://example.test",
        json={"a": 1},
        headers={"Authorization": "Token"},
    )
    assert result is response


def test_request_post_ssl_error(monkeypatch):
    coordinator = build_coordinator()
    coordinator.verify_ssl = True

    def fake_post(url, *, json=None, data=None, headers=None, verify=None, timeout=None):
        raise requests.exceptions.SSLError("ssl failure")

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.post", fake_post
    )

    with pytest.raises(UpdateFailed) as exc:
        coordinator._request_post("https://example.test")
    assert "disable verify_ssl" in str(exc.value)


def test_request_post_http_auth_error(monkeypatch):
    coordinator = build_coordinator()

    def fake_post(url, *, json=None, data=None, headers=None, verify=None, timeout=None):
        raise requests.exceptions.HTTPError(
            response=SimpleNamespace(status_code=401)
        )

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.post", fake_post
    )

    with pytest.raises(AuthenticationFailed):
        coordinator._request_post("https://example.test")


def test_request_post_timeout(monkeypatch):
    coordinator = build_coordinator()

    def fake_post(url, *, json=None, data=None, headers=None, verify=None, timeout=None):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.post", fake_post
    )

    with pytest.raises(UpdateFailed) as exc:
        coordinator._request_post("https://example.test")
    assert "Request timeout" in str(exc.value)


def test_set_config_value_success(monkeypatch):
    coordinator = build_coordinator()
    calls = []

    def fake_request_post(url, *, json=None, data=None, headers=None):
        calls.append((url, json, headers))
        return DummyResponse({}, status_code=200)

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    result = coordinator.set_config_value("20001", 3.2)

    assert result is True
    assert len(calls) == 1
    url, payload, headers = calls[0]
    assert url.startswith("https://1.2.3.4:32800/rest/neteco/web/homemgr/v1/device/set-config-info")
    assert payload["changeValues"][0] == {"id": 20001, "value": 3.2}
    assert headers is not coordinator.headers  # copy made


def test_set_config_value_reauth_flow(monkeypatch):
    coordinator = build_coordinator()
    sleep_calls = []
    post_calls = []

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )

    def fake_request_post(url, *, json=None, data=None, headers=None):
        post_calls.append((url, json))
        if len(post_calls) == 1:
            raise AuthenticationFailed("expired")
        return DummyResponse({}, status_code=200)

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    def fake_authenticate():
        coordinator.region_ip = "1.2.3.4"
        coordinator.wallbox_dn_id = "wallbox"
        coordinator.headers = {"Auth": "token"}

    coordinator.authenticate = fake_authenticate

    coordinator.token = "expired"
    coordinator.headers = {"Auth": "old"}
    coordinator.region_ip = "stale"
    coordinator.wallbox_dn_id = "stale"

    result = coordinator.set_config_value("20001", 2.5)

    assert result is True
    assert sleep_calls == [1]
    assert len(post_calls) == 2
