from types import SimpleNamespace

import pytest
import requests

from custom_components.huawei_charger.coordinator import (
    AuthenticationFailed,
    FusionSolarRequestError,
    HuaweiChargerCoordinator,
    UpdateFailed,
)
from custom_components.huawei_charger.const import (
    DEFAULT_FUSIONSOLAR_HOST,
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE_OFFSET,
)


def build_coordinator(language="en-US", time_zone="UTC"):
    scheduled_calls = []
    coordinator = object.__new__(HuaweiChargerCoordinator)
    coordinator.hass = SimpleNamespace(
        config=SimpleNamespace(language=language, time_zone=time_zone),
        loop=SimpleNamespace(
            call_soon_threadsafe=lambda func, *args: scheduled_calls.append((func, args))
        ),
    )
    coordinator.entry = SimpleNamespace(data={}, options={})
    coordinator.verify_ssl = False
    coordinator.enable_logging = True
    coordinator.request_timeout = 15
    coordinator.username = "user"
    coordinator.password = "password"
    coordinator.token = "token"
    coordinator.headers = {"Auth": "token"}
    coordinator.region_ip = "1.2.3.4"
    coordinator.auth_host = DEFAULT_FUSIONSOLAR_HOST
    coordinator.dn_id = "station"
    coordinator.wallbox_dn = "NE=168363665"
    coordinator.wallbox_dn_id = "wallbox"
    coordinator.station_values = {}
    coordinator.param_values = {}
    coordinator.config_signal_details = {}
    coordinator.config_signal_values = {}
    coordinator.locale = DEFAULT_LOCALE
    coordinator.timezone_offset = DEFAULT_TIMEZONE_OFFSET
    coordinator._request_counter = 0
    coordinator._last_realtime_signal_catalog = None
    coordinator._last_config_signal_catalog = None
    coordinator._history_probe_completed = False
    coordinator._scheduled_calls = scheduled_calls
    coordinator.debug_data = coordinator._build_debug_data()
    return coordinator


class FailingJsonResponse:
    def json(self):
        raise ValueError("bad json")


class DummyResponse:
    def __init__(self, payload=None, status_code=200, text=None):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text if text is not None else str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


def test_derive_locale_variants():
    coordinator = build_coordinator(language="en-US")
    assert coordinator._derive_locale() == "en_US"

    coordinator.hass.config.language = "fr"
    assert coordinator._derive_locale() == "fr_FR"

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


def test_request_get_success(monkeypatch):
    coordinator = build_coordinator()
    response = DummyResponse({"ok": True}, status_code=200)

    def fake_get(url, *, params=None, headers=None, verify=None, timeout=None):
        assert params == {"deviceDn": "NE=1"}
        assert verify is coordinator.verify_ssl
        assert timeout == coordinator.request_timeout
        return response

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.get", fake_get
    )

    result = coordinator._request_get(
        "https://example.test",
        params={"deviceDn": "NE=1"},
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
        return DummyResponse(
            {"accessToken": "secret-token", "message": "expired"},
            status_code=401,
        )

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.requests.post", fake_post
    )

    with pytest.raises(AuthenticationFailed) as exc:
        coordinator._request_post("https://example.test")
    assert "secret-token" not in str(exc.value)
    assert "***" in str(exc.value)


def test_response_headers_excerpt_masks_sensitive_headers():
    coordinator = build_coordinator()
    response = DummyResponse({"ok": True})
    response.headers = {
        "Set-Cookie": "bspsession=secret; Path=/",
        "roaRand": "csrf-secret",
        "Content-Type": "application/json",
    }

    excerpt = coordinator._response_headers_excerpt(response)

    assert "secret" not in excerpt
    assert "***" in excerpt


def test_json_dump_masks_refresh_token():
    coordinator = build_coordinator()

    dumped = coordinator._json_dump({"data": {"refreshToken": "very-secret"}})

    assert "very-secret" not in dumped
    assert "***" in dumped


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


def test_authenticate_uses_entry_host_when_region_missing(monkeypatch):
    coordinator = build_coordinator()
    coordinator.auth_host = "uni005eu5.fusionsolar.huawei.com"
    station_calls = []

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        assert url.startswith("https://uni005eu5.fusionsolar.huawei.com:32800/")
        return DummyResponse({"data": {"accessToken": "tenant-token"}})

    coordinator._request_post = fake_request_post
    coordinator.fetch_station_dn = lambda: station_calls.append(True)

    coordinator.authenticate()

    assert coordinator.token == "tenant-token"
    assert coordinator.region_ip == "uni005eu5.fusionsolar.huawei.com"
    assert "bspsession=tenant-token" in coordinator.headers["Cookie"]
    assert station_calls == [True]


def test_authenticate_retries_default_host_when_tenant_host_has_no_token(monkeypatch):
    coordinator = build_coordinator()
    coordinator.auth_host = "uni005eu5.fusionsolar.huawei.com"
    post_calls = []
    station_calls = []

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        post_calls.append(url)
        if "uni005eu5.fusionsolar.huawei.com" in url:
            return DummyResponse({"data": {"message": "migrated"}})
        return DummyResponse(
            {"data": {"accessToken": "intl-token", "regionFloatIp": "5.6.7.8"}}
        )

    coordinator._request_post = fake_request_post
    coordinator.fetch_station_dn = lambda: station_calls.append(True)

    coordinator.authenticate()

    assert post_calls == [
        "https://uni005eu5.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token",
        "https://intl.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token",
    ]
    assert coordinator.token == "intl-token"
    assert coordinator.region_ip == "5.6.7.8"
    assert station_calls == [True]


def test_fetch_station_dn_stores_charge_store():
    coordinator = build_coordinator()
    coordinator._request_post = lambda *args, **kwargs: DummyResponse(
        {
            "data": {
                "list": [
                    {
                        "dn": "NE=149170766",
                        "chargeStore": "Connected",
                    }
                ]
            }
        }
    )

    coordinator.fetch_station_dn()

    assert coordinator.dn_id == "NE=149170766"
    assert coordinator.station_values == {"charge_store": "Connected"}


def test_fetch_station_dn_prefers_configured_station():
    coordinator = build_coordinator()
    coordinator.preferred_station_dn = "NE=station-2"
    coordinator._request_post = lambda *args, **kwargs: DummyResponse(
        {
            "data": {
                "list": [
                    {"dn": "NE=station-1", "chargeStore": "Idle"},
                    {"dn": "NE=station-2", "chargeStore": "Connected"},
                ]
            }
        }
    )

    coordinator.fetch_station_dn()

    assert coordinator.dn_id == "NE=station-2"
    assert coordinator.station_values == {"charge_store": "Connected"}


def test_fetch_wallbox_info_falls_back_to_realtime_data():
    coordinator = build_coordinator()
    coordinator.dn_id = "NE=149170766"
    coordinator.wallbox_dn = None
    coordinator.wallbox_dn_id = None
    coordinator._request_post = lambda *args, **kwargs: DummyResponse(
        {
            "code": 0,
            "data": [
                {
                    "dn": "NE=168363665",
                    "dnId": 118509961,
                    "paramValues": {
                        "10001": "v1",
                        "50009": "1",
                    },
                }
            ],
        }
    )
    coordinator._request_get = lambda *args, **kwargs: DummyResponse(
        {
            "data": [
                {"id": "20012", "value": "40"},
                {"signalId": "20017", "signalValue": "true"},
                {"id": "538976598", "value": "7.4"},
            ]
        }
    )

    result = coordinator.fetch_wallbox_info()

    assert coordinator.wallbox_dn == "NE=168363665"
    assert coordinator.wallbox_dn_id == 118509961
    assert result["20012"] == 40
    assert result["20017"] is True
    assert coordinator.config_signal_values["538976598"] == 7.4


def test_fetch_wallbox_info_keeps_config_values_separate_from_runtime_values():
    coordinator = build_coordinator()
    coordinator.dn_id = "NE=149170766"
    coordinator._request_post = lambda *args, **kwargs: DummyResponse(
        {
            "code": 0,
            "data": [
                {
                    "dn": "NE=168363665",
                    "dnId": 118509961,
                    "paramValues": {
                        "10001": "v1",
                    },
                }
            ],
        }
    )
    def fake_fetch_wallbox_config_probe():
        coordinator.config_signal_values = {
            "20001": 4.0,
            "538976598": 7.4,
        }
        return coordinator.config_signal_values

    coordinator.fetch_wallbox_config_probe = fake_fetch_wallbox_config_probe
    coordinator.fetch_wallbox_realtime_data = lambda: {"10008": 12.34}

    result = coordinator.fetch_wallbox_info()

    assert result["10008"] == 12.34
    assert coordinator.config_signal_values == {
        "20001": 4.0,
        "538976598": 7.4,
    }


def test_fetch_wallbox_info_prefers_configured_wallbox():
    coordinator = build_coordinator()
    coordinator.dn_id = "NE=149170766"
    coordinator.preferred_wallbox_dn = "NE=wallbox-2"
    coordinator.fetch_wallbox_config_probe = lambda: {}
    coordinator.fetch_wallbox_realtime_data = lambda: {}
    coordinator._request_post = lambda *args, **kwargs: DummyResponse(
        {
            "code": 0,
            "data": [
                {
                    "dn": "NE=wallbox-1",
                    "dnId": 111,
                    "deviceStatus": "1",
                    "paramValues": {"10003": "7.4"},
                },
                {
                    "dn": "NE=wallbox-2",
                    "dnId": 222,
                    "deviceStatus": "3",
                    "paramValues": {"10003": "11"},
                },
            ],
        }
    )

    result = coordinator.fetch_wallbox_info()

    assert coordinator.wallbox_dn == "NE=wallbox-2"
    assert coordinator.wallbox_dn_id == 222
    assert result["device_status"] == "3"
    assert result["10003"] == 11


def test_fetch_wallbox_config_probe_uses_dn_get_shape():
    coordinator = build_coordinator()
    coordinator.wallbox_dn = "NE=168363665"
    coordinator.wallbox_dn_id = 118509961
    calls = []

    def fake_request_get(url, *, params=None, headers=None, operation=None):
        calls.append(("GET", url, params, operation))
        return DummyResponse({"data": [{"id": "20001", "name": "Dynamic Power Limit", "value": "4.0"}]})

    coordinator._request_get = fake_request_get

    coordinator.fetch_wallbox_config_probe()

    assert coordinator.config_signal_values == {"20001": 4.0}
    assert [call[3] for call in calls] == [
        "wallbox-config-get-dn",
    ]


def test_extract_config_signal_catalog_collects_writable_metadata():
    coordinator = build_coordinator()

    payload = {
        "data": [
            {
                "signals": [
                    {
                        "id": "20001",
                        "name": "Dynamic Power Limit",
                        "unit": "kW",
                        "writable": True,
                        "minValue": "1.6",
                        "maxValue": "7.4",
                        "step": "0.1",
                        "options": ["1.6", "3.2", "7.4"],
                    },
                    {
                        "signalId": "538976598",
                        "label": "Fixed Max Charging Power",
                        "readOnly": False,
                        "rwFlag": "RW",
                        "defaultValue": "7.4",
                    },
                ]
            }
        ]
    }

    result = coordinator._extract_config_signal_catalog(payload)

    assert result == [
        {
            "id": "20001",
            "name": "Dynamic Power Limit",
            "unit": "kW",
            "value": None,
            "default": None,
            "writable": True,
            "read_only": None,
            "rw_flag": None,
            "min": "1.6",
            "max": "7.4",
            "step": "0.1",
            "options": ["1.6", "3.2", "7.4"],
            "range": None,
        },
        {
            "id": "538976598",
            "name": "Fixed Max Charging Power",
            "unit": None,
            "value": None,
            "default": "7.4",
            "writable": None,
            "read_only": False,
            "rw_flag": "RW",
            "min": None,
            "max": None,
            "step": None,
            "options": None,
            "range": None,
        },
    ]


def test_extract_signal_values_collects_common_signal_shapes():
    coordinator = build_coordinator()

    payload = {
        "data": {
            "signals": [
                {"id": "20012", "value": "40"},
                {"signalId": "20017", "signalValue": "true"},
                {"signalID": "10008", "realValue": "12.34"},
                {"signal_id": "10010", "currentValue": "5"},
                {"id": "10009", "val": "1.5"},
            ]
        }
    }

    result = coordinator._extract_signal_values(payload)

    assert result == {
        "20012": "40",
        "20017": "true",
        "10008": "12.34",
        "10010": "5",
        "10009": "1.5",
    }


def test_extract_signal_catalog_collects_group_name_and_unit():
    coordinator = build_coordinator()

    payload = {
        "data": [
            {
                "groupName": "Grundlegende Informationen",
                "signals": [
                    {"id": 10003, "name": "Nennleistung", "unit": "kW"},
                    {"id": 10008, "name": "Gesamtgeladene Energie", "unit": "kWh"},
                ],
            }
        ]
    }

    result = coordinator._extract_signal_catalog(payload)

    assert result == [
        {
            "id": "10003",
            "name": "Nennleistung",
            "unit": "kW",
            "group": "Grundlegende Informationen",
        },
        {
            "id": "10008",
            "name": "Gesamtgeladene Energie",
            "unit": "kWh",
            "group": "Grundlegende Informationen",
        },
    ]


def test_history_probe_signal_ids_prefers_known_and_realtime_registers():
    coordinator = build_coordinator()

    result = coordinator._history_probe_signal_ids(["10008", "10012", "20012"])

    assert result[:5] == ["10008", "10009", "10010", "20017", "538976598"]
    assert "10012" in result


def test_fetch_wallbox_history_probe_marks_completed(monkeypatch):
    coordinator = build_coordinator()
    coordinator.wallbox_dn = "NE=168363665"
    calls = []

    def fake_request_get(url, *, params=None, headers=None, operation=None):
        calls.append((url, params, operation))
        return DummyResponse({"data": [{"signalId": "10008"}]})

    coordinator._request_get = fake_request_get

    coordinator.fetch_wallbox_history_probe(["10008", "10012"])

    assert coordinator._history_probe_completed is True
    assert calls
    url, params, operation = calls[0]
    assert url.endswith("/rest/pvms/web/device/v1/device-history-data")
    assert operation == "wallbox-history"
    assert ("deviceDn", "NE=168363665") in params
    assert ("signalIds", "10008") in params


def test_set_config_value_success(monkeypatch):
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}
    calls = []

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        calls.append((url, json, data, headers))
        return DummyResponse({}, status_code=200)

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    result = coordinator.set_config_value("20001", 3.2)

    assert result is True
    assert len(calls) == 1
    url, payload_json, payload_data, headers = calls[0]
    assert url.startswith("https://1.2.3.4:32800/rest/pvms/web/device/v1/deviceExt/set-config-signals")
    assert payload_json is None
    assert payload_data["dn"] == "NE=168363665"
    assert payload_data["changeValues"] == '[{"id":"20001","value":"3.2"}]'
    assert headers is not coordinator.headers  # copy made
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert coordinator._scheduled_calls
    assert coordinator.param_values["20001"] == 3.2
    assert coordinator.config_signal_values["20001"] == 3.2


def test_set_config_value_rejects_error_payloads():
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}
    sleep_calls = []

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )

    coordinator._request_post = lambda *args, **kwargs: DummyResponse({}, status_code=200)
    coordinator._json_or_error = lambda response, context, default=None: {"errorCode": "9"}

    result = coordinator.set_config_value("20001", 3.2)

    monkeypatch.undo()

    assert result is False
    assert sleep_calls == [1, 2]


def test_set_config_value_returns_error_when_new_endpoint_fails():
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}
    calls = []
    sleep_calls = []

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        calls.append((url, json, data, operation))
        raise FusionSolarRequestError("new endpoint failed")

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    result = coordinator.set_config_value("20001", 3.2)

    monkeypatch.undo()

    assert result is False
    assert [call[3] for call in calls] == [
        "set-config-new:20001",
        "set-config-new:20001",
        "set-config-new:20001",
    ]
    assert sleep_calls == [1, 2]


def test_set_config_value_reauth_flow(monkeypatch):
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}
    sleep_calls = []
    post_calls = []

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        post_calls.append((url, json, data))
        if len(post_calls) == 1:
            raise AuthenticationFailed("expired")
        return DummyResponse({}, status_code=200)

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    def fake_authenticate():
        coordinator.region_ip = "5.6.7.8"
        coordinator.wallbox_dn = "NE=168363665"
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
    assert post_calls[1][0].startswith("https://5.6.7.8:32800/")
    assert post_calls[1][1] is None
    assert post_calls[1][2]["dn"] == "NE=168363665"


def test_set_config_value_recovers_wallbox_context_after_reauth(monkeypatch):
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}
    sleep_calls = []
    post_calls = []
    fetch_calls = []

    monkeypatch.setattr(
        "custom_components.huawei_charger.coordinator.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )

    def fake_request_post(url, *, json=None, data=None, headers=None, operation=None):
        post_calls.append((url, json, data))
        if len(post_calls) == 1:
            raise AuthenticationFailed("expired")
        return DummyResponse({}, status_code=200)

    coordinator._request_post = fake_request_post
    coordinator._json_or_error = lambda response, context, default=None: {}

    def fake_authenticate():
        coordinator.region_ip = "5.6.7.8"
        coordinator.headers = {"Auth": "token"}
        coordinator.dn_id = "station"

    def fake_fetch_wallbox_info():
        fetch_calls.append(True)
        coordinator.wallbox_dn = "NE=wallbox-restored"
        coordinator.wallbox_dn_id = "wallbox-restored"
        coordinator.param_values = {"20001": 2.5, "538976598": 7.4}
        coordinator._update_register_debug_state()
        return coordinator.param_values

    coordinator.authenticate = fake_authenticate
    coordinator.fetch_wallbox_info = fake_fetch_wallbox_info

    coordinator.token = "expired"
    coordinator.headers = {"Auth": "old"}
    coordinator.region_ip = "stale"
    coordinator.wallbox_dn_id = "stale"

    result = coordinator.set_config_value("20001", 2.5)

    assert result is True
    assert sleep_calls == [1]
    assert len(fetch_calls) == 1
    assert post_calls[1][0].startswith("https://5.6.7.8:32800/")
    assert post_calls[1][1] is None
    assert post_calls[1][2]["dn"] == "NE=wallbox-restored"


def test_update_register_debug_state_tracks_writable_registers():
    coordinator = build_coordinator()
    coordinator.param_values = {"20001": 2.5, "10009": 1.2}

    coordinator._update_register_debug_state()

    assert coordinator.debug_data["last_register_count"] == 2
    assert coordinator.debug_data["writable_registers_available"] == ["20001"]
    assert coordinator.debug_data["missing_writable_registers"] == ["538976598"]
    assert coordinator._scheduled_calls


def test_record_update_debug_schedules_coordinator_update():
    coordinator = build_coordinator()
    coordinator.data = {"10008": 1.2}

    coordinator._record_update_debug(
        status="error",
        error="boom",
        duration_ms=123,
    )

    assert coordinator._scheduled_calls
    callback, args = coordinator._scheduled_calls[-1]
    assert callback == coordinator.async_set_updated_data
    assert args == (coordinator.data,)


def test_record_write_debug_schedules_coordinator_update():
    coordinator = build_coordinator()
    coordinator.data = {"20001": 2.5}

    coordinator._record_write_debug(
        status="error",
        param_id="20001",
        value=3.2,
        error="boom",
        attempts=1,
    )

    assert coordinator._scheduled_calls
    callback, args = coordinator._scheduled_calls[-1]
    assert callback == coordinator.async_set_updated_data
    assert args == (coordinator.data,)


def test_clear_register_debug_state_resets_snapshot():
    coordinator = build_coordinator()
    coordinator.param_values = {"20001": 2.5}
    coordinator._update_register_debug_state()

    coordinator._clear_register_debug_state()

    assert coordinator.debug_data["last_register_count"] == 0
    assert coordinator.debug_data["available_registers"] == []
    assert coordinator.debug_data["writable_registers_available"] == []
    assert coordinator.debug_data["missing_writable_registers"] == ["538976598", "20001"]


def test_fusion_solar_request_error_includes_response_excerpt():
    error = FusionSolarRequestError("HTTP 500 error", response_excerpt='{"code":"x"}')

    assert error.response_excerpt == '{"code":"x"}'


@pytest.mark.parametrize(
    ("update_error", "write_error", "expected"),
    [
        ("HTTP 403 authentication error from FusionSolar", None, True),
        (None, "Invalid username or password", True),
        ("Connection timeout while contacting API", None, False),
        (None, None, False),
    ],
)
def test_is_reauth_required(update_error, write_error, expected):
    coordinator = build_coordinator()
    coordinator.debug_data["last_update_error"] = update_error
    coordinator.debug_data["last_write_error"] = write_error

    assert coordinator.is_reauth_required() is expected
