import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

from custom_components.huawei_charger.config_flow import (
    HuaweiChargerConfigFlow,
    HuaweiChargerOptionsFlow,
)
from custom_components.huawei_charger.const import (
    CONF_ENABLE_LOGGING,
    CONF_INTERVAL,
    DEFAULT_FUSIONSOLAR_HOST,
)


def test_normalize_host_defaults_to_intl():
    assert HuaweiChargerConfigFlow._normalize_host("") == DEFAULT_FUSIONSOLAR_HOST


def test_normalize_host_accepts_plain_hostname():
    assert (
        HuaweiChargerConfigFlow._normalize_host("uni005eu5.fusionsolar.huawei.com")
        == "uni005eu5.fusionsolar.huawei.com"
    )


def test_normalize_host_extracts_hostname_from_full_url():
    assert (
        HuaweiChargerConfigFlow._normalize_host(
            "https://uni005eu5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms"
        )
        == "uni005eu5.fusionsolar.huawei.com"
    )


def test_build_unique_id():
    assert (
        HuaweiChargerConfigFlow._build_unique_id(
            "User@Example.com", "UNI005EU5.FUSIONSOLAR.HUAWEI.COM"
        )
        == "user@example.com@uni005eu5.fusionsolar.huawei.com"
    )


def test_options_flow_uses_current_home_assistant_base_class():
    assert issubclass(HuaweiChargerOptionsFlow, config_entries.OptionsFlow)


def test_validate_credentials_retries_default_host_when_tenant_host_has_no_token(monkeypatch):
    flow = HuaweiChargerConfigFlow()
    calls = []

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, *, json=None, verify=None, headers=None, timeout=None):
        calls.append(url)
        if "uni005eu5.fusionsolar.huawei.com" in url:
            return DummyResponse({"data": {"message": "migrated"}})
        return DummyResponse({"data": {"accessToken": "token"}})

    monkeypatch.setattr(
        "custom_components.huawei_charger.config_flow.requests.post",
        fake_post,
    )

    flow._validate_credentials(
        "uni005eu5.fusionsolar.huawei.com",
        "user",
        "password",
        False,
    )

    assert calls == [
        "https://uni005eu5.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token",
        "https://intl.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token",
    ]


def test_reauth_initial_context_without_host_shows_form():
    flow = HuaweiChargerConfigFlow()
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={CONF_USERNAME: "user", CONF_HOST: DEFAULT_FUSIONSOLAR_HOST},
        options={},
    )
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_entry=lambda entry_id: entry)
    )
    flow.context = {"entry_id": entry.entry_id}
    flow.async_show_form = lambda **kwargs: kwargs

    result = asyncio.run(
        flow.async_step_reauth(
            {
                CONF_USERNAME: "user",
                CONF_PASSWORD: "old-password",
            }
        )
    )

    assert result["step_id"] == "reauth"
    assert CONF_HOST in result["data_schema"].schema


def test_options_flow_updates_host_from_active_integration():
    flow = HuaweiChargerOptionsFlow()
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: DEFAULT_FUSIONSOLAR_HOST,
        },
        options={
            CONF_INTERVAL: 30,
            CONF_VERIFY_SSL: False,
            CONF_ENABLE_LOGGING: True,
        },
        title="user@example.com @ intl.fusionsolar.huawei.com",
        unique_id="user@example.com@intl.fusionsolar.huawei.com",
    )
    async_update_entry = MagicMock()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry_id: entry,
            async_entries=lambda domain: [entry],
            async_update_entry=async_update_entry,
        )
    )
    flow._config_entry = entry
    flow.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        flow.async_step_init(
            {
                CONF_HOST: "https://uni005eu5.fusionsolar.huawei.com/path",
                CONF_INTERVAL: 60,
                CONF_VERIFY_SSL: True,
                CONF_ENABLE_LOGGING: False,
            }
        )
    )

    async_update_entry.assert_called_once_with(
        entry,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: "uni005eu5.fusionsolar.huawei.com",
        },
        options={
            CONF_INTERVAL: 60,
            CONF_VERIFY_SSL: True,
            CONF_ENABLE_LOGGING: False,
        },
        title="user@example.com @ uni005eu5.fusionsolar.huawei.com",
        unique_id="user@example.com@uni005eu5.fusionsolar.huawei.com",
    )
    assert result == {"title": "", "data": {}}


def test_options_schema_includes_logging_toggle():
    flow = HuaweiChargerOptionsFlow()
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={CONF_HOST: DEFAULT_FUSIONSOLAR_HOST},
        options={CONF_ENABLE_LOGGING: False},
    )
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_entry=lambda entry_id: entry)
    )
    flow._config_entry = entry

    schema = flow._options_schema(entry)

    assert CONF_ENABLE_LOGGING in schema.schema


def test_options_flow_missing_logging_value_turns_logging_off():
    flow = HuaweiChargerOptionsFlow()
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: DEFAULT_FUSIONSOLAR_HOST,
        },
        options={
            CONF_INTERVAL: 30,
            CONF_VERIFY_SSL: True,
            CONF_ENABLE_LOGGING: True,
        },
        title="user@example.com @ intl.fusionsolar.huawei.com",
        unique_id="user@example.com@intl.fusionsolar.huawei.com",
    )
    async_update_entry = MagicMock()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry_id: entry,
            async_entries=lambda domain: [entry],
            async_update_entry=async_update_entry,
        )
    )
    flow._config_entry = entry
    flow.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        flow.async_step_init(
            {
                CONF_HOST: "uni005eu5.fusionsolar.huawei.com",
                CONF_INTERVAL: 60,
                CONF_VERIFY_SSL: True,
            }
        )
    )

    async_update_entry.assert_called_once_with(
        entry,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: "uni005eu5.fusionsolar.huawei.com",
        },
        options={
            CONF_INTERVAL: 60,
            CONF_VERIFY_SSL: True,
            CONF_ENABLE_LOGGING: False,
        },
        title="user@example.com @ uni005eu5.fusionsolar.huawei.com",
        unique_id="user@example.com@uni005eu5.fusionsolar.huawei.com",
    )
    assert result == {"title": "", "data": {}}


def test_options_flow_string_false_turns_logging_off():
    flow = HuaweiChargerOptionsFlow()
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: DEFAULT_FUSIONSOLAR_HOST,
        },
        options={
            CONF_INTERVAL: 30,
            CONF_VERIFY_SSL: True,
            CONF_ENABLE_LOGGING: True,
        },
        title="user@example.com @ intl.fusionsolar.huawei.com",
        unique_id="user@example.com@intl.fusionsolar.huawei.com",
    )
    async_update_entry = MagicMock()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry_id: entry,
            async_entries=lambda domain: [entry],
            async_update_entry=async_update_entry,
        )
    )
    flow._config_entry = entry
    flow.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        flow.async_step_init(
            {
                CONF_HOST: "uni005eu5.fusionsolar.huawei.com",
                CONF_INTERVAL: 60,
                CONF_VERIFY_SSL: "false",
                CONF_ENABLE_LOGGING: "false",
            }
        )
    )

    async_update_entry.assert_called_once_with(
        entry,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_HOST: "uni005eu5.fusionsolar.huawei.com",
        },
        options={
            CONF_INTERVAL: 60,
            CONF_VERIFY_SSL: False,
            CONF_ENABLE_LOGGING: False,
        },
        title="user@example.com @ uni005eu5.fusionsolar.huawei.com",
        unique_id="user@example.com@uni005eu5.fusionsolar.huawei.com",
    )
    assert result == {"title": "", "data": {}}
