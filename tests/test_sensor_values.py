from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.huawei_charger import binary_sensor
from custom_components.huawei_charger.binary_sensor import (
    HuaweiChargerCredentialsRejectedBinarySensor,
)
from custom_components.huawei_charger.const import DOMAIN
from custom_components.huawei_charger.sensor import (
    HuaweiChargerDebugSensor,
    HuaweiChargerSensor,
    _active_sensor_registers,
)


class DummyCoordinator:
    """Minimal coordinator stub for unit tests."""

    def __init__(self, data, entry_id="test_entry", last_update_success=True):
        self.data = data
        self.entry = SimpleNamespace(entry_id=entry_id)
        self.last_update_success = last_update_success
        self.debug_data = {
            "last_update_status": "success",
            "last_update_error": None,
            "last_update_at": "2026-03-21T10:00:00Z",
            "last_update_duration_ms": 120,
            "last_update_response_excerpt": "{\"message\":\"ok\"}",
            "last_register_count": 2,
            "writable_registers_available": ["20001"],
            "missing_writable_registers": ["538976598"],
            "available_registers": ["10009", "20001"],
            "last_write_status": "error",
            "last_write_param_id": "20001",
            "last_write_value": 2.5,
            "last_write_error": "HTTP 403 authentication error from FusionSolar",
            "last_write_at": "2026-03-21T10:01:00Z",
            "last_write_duration_ms": 250,
            "last_write_attempts": 3,
            "last_write_response_excerpt": "{\"failCode\":403}",
        }

    def async_add_listener(self, update_callback):
        # CoordinatorEntity expects a callable that removes the listener
        return lambda: None

    def get_register_value(self, reg_id):
        return self.data.get(str(reg_id))


def test_power_sensor_converts_watts_to_kw():
    coordinator = DummyCoordinator({"538976570": 7400})
    sensor = HuaweiChargerSensor(coordinator, "538976570")

    assert sensor.native_value == pytest.approx(7.4)


def test_current_power_sensor_uses_power_value():
    coordinator = DummyCoordinator({"current_power": 3.7})
    sensor = HuaweiChargerSensor(coordinator, "current_power")

    assert sensor.name == "Current Power"
    assert sensor.native_value == pytest.approx(3.7)


def test_voltage_sensor_rounds_to_one_decimal():
    coordinator = DummyCoordinator({"2101259": 231})
    sensor = HuaweiChargerSensor(coordinator, "2101259")

    assert sensor.native_value == pytest.approx(231.0)


def test_network_mode_sensor_returns_raw_numeric_value():
    coordinator = DummyCoordinator({"20014": 1})
    sensor = HuaweiChargerSensor(coordinator, "20014", is_diagnostic=True)

    assert sensor.name == "Network Mode"
    assert sensor.native_value == 1


def test_device_info_sensor_extracts_summary():
    raw_info = (
        "/$[ArchivesInfo Version]\r\n"
        "/$ArchivesInfoVersion=3.0\r\n\r\n\r\n"
        "[Board Properties]\r\n"
        "BoardType=SCharger-7KS-S0\r\n"
        "BarCode=NS2321103987\r\n"
        "VendorName=Huawei\r\n"
        "Model=SCharger-7KS-S0\r\n"
    )
    coordinator = DummyCoordinator({"2101251": raw_info})
    sensor = HuaweiChargerSensor(coordinator, "2101251", is_diagnostic=True)

    assert sensor.native_value == "SCharger-7KS-S0 - SCharger-7KS-S0 - Huawei"


def test_sensor_availability_requires_value():
    coordinator = DummyCoordinator({"20017": True})
    sensor = HuaweiChargerSensor(coordinator, "20017")

    assert sensor.available is True

    coordinator_missing = DummyCoordinator({}, last_update_success=True)
    sensor_missing = HuaweiChargerSensor(coordinator_missing, "20017")
    assert sensor_missing.available is False


def test_sensor_stays_available_with_stale_cached_value():
    coordinator = DummyCoordinator({"20017": True}, last_update_success=False)
    sensor = HuaweiChargerSensor(coordinator, "20017")

    assert sensor.available is True
    assert sensor.extra_state_attributes["stale"] is True


def test_sensor_extra_state_attributes():
    coordinator = DummyCoordinator({"538976598": 7.4})
    sensor = HuaweiChargerSensor(coordinator, "538976598")

    attrs = sensor.extra_state_attributes
    assert attrs["register_id"] == "538976598"
    assert attrs["raw_value"] == 7.4
    assert attrs["stale"] is False


def test_sensitive_register_is_masked_and_unavailable():
    coordinator = DummyCoordinator({"20034": "secret"})
    sensor = HuaweiChargerSensor(coordinator, "20034", is_diagnostic=True)

    assert sensor.available is False
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["raw_value"] == "***"


def test_debug_update_sensor_attributes():
    coordinator = DummyCoordinator({"20017": True})
    sensor = HuaweiChargerDebugSensor(coordinator, "update")

    assert sensor.native_value == "success"
    attrs = sensor.extra_state_attributes
    assert attrs["last_register_count"] == 2
    assert attrs["last_update_response_excerpt"] == "{\"message\":\"ok\"}"
    assert attrs["missing_writable_registers"] == ["538976598"]


def test_debug_write_sensor_attributes():
    coordinator = DummyCoordinator({"20017": True})
    sensor = HuaweiChargerDebugSensor(coordinator, "write")

    assert sensor.native_value == "error"
    attrs = sensor.extra_state_attributes
    assert attrs["last_write_param_id"] == "20001"
    assert attrs["last_write_attempts"] == 3
    assert attrs["last_write_response_excerpt"] == "{\"failCode\":403}"


def test_credentials_rejected_binary_sensor_on():
    coordinator = DummyCoordinator({"20017": True})
    coordinator.is_reauth_required = lambda: True
    sensor = HuaweiChargerCredentialsRejectedBinarySensor(coordinator)

    assert sensor.is_on is True
    assert sensor.name == "Reauthentication Required"
    attrs = sensor.extra_state_attributes
    assert "Reconfigure the integration credentials" in attrs["suggested_action"]
    assert attrs["last_write_error"] == "HTTP 403 authentication error from FusionSolar"


def test_credentials_rejected_binary_sensor_off():
    coordinator = DummyCoordinator({"20017": True})
    coordinator.debug_data["last_write_error"] = None
    coordinator.debug_data["last_update_error"] = None
    coordinator.is_reauth_required = lambda: False
    sensor = HuaweiChargerCredentialsRejectedBinarySensor(coordinator)

    assert sensor.is_on is False


@pytest.mark.asyncio
async def test_binary_sensor_setup_removes_legacy_auth_sensor(monkeypatch):
    coordinator = DummyCoordinator({"20017": True})
    entry = SimpleNamespace(entry_id="test_entry")
    registry = MagicMock()
    registry_entries = [
        SimpleNamespace(
            domain="binary_sensor",
            unique_id="test_entry_credentials_rejected",
            entity_id="binary_sensor.huawei_charger_credentials_rejected",
        ),
        SimpleNamespace(
            domain="binary_sensor",
            unique_id="test_entry_reauthentication_required",
            entity_id="binary_sensor.huawei_charger_reauthentication_required",
        ),
    ]
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coordinator}})
    added_entities = []

    monkeypatch.setattr(binary_sensor.er, "async_get", lambda hass_arg: registry)
    monkeypatch.setattr(
        binary_sensor.er,
        "async_entries_for_config_entry",
        lambda registry_arg, entry_id: registry_entries,
    )

    await binary_sensor.async_setup_entry(
        hass,
        entry,
        lambda entities: added_entities.extend(entities),
    )

    registry.async_remove.assert_called_once_with(
        "binary_sensor.huawei_charger_credentials_rejected"
    )
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "test_entry_reauthentication_required"


def test_active_sensor_registers_only_returns_present_registers():
    main, diagnostic = _active_sensor_registers(
        {
            "current_power": 3.7,
            "10008": 1.2,
            "20012": 40,
            "10007": "model",
            "99999": "ignore",
        },
        {
            "20001": 4.0,
            "538976598": 7.4,
            "33595393": "SCharger",
        },
    )

    assert main == ["current_power", "10008"]
    assert diagnostic == ["10007", "20012", "99999", "33595393"]


def test_active_sensor_registers_preserves_existing_ids_and_skips_sensitive():
    main, diagnostic = _active_sensor_registers(
        {"current_power": 3.7},
        {"20034": "secret"},
        existing_register_ids={"20012", "20034", "10007"},
    )

    assert main == ["current_power"]
    assert diagnostic == ["10007", "20012"]


def test_active_sensor_registers_does_not_keep_missing_registry_ids_by_default():
    main, diagnostic = _active_sensor_registers(
        {"current_power": 3.7},
        None,
    )

    assert main == ["current_power"]
    assert diagnostic == []


def test_known_diagnostic_register_uses_mapped_name():
    coordinator = DummyCoordinator({"10007": "SCharger-7KS-S0"})
    sensor = HuaweiChargerSensor(coordinator, "10007", is_diagnostic=True)

    assert sensor.name == "Model"


def test_unknown_diagnostic_register_keeps_raw_name():
    coordinator = DummyCoordinator({"10047": 6})
    sensor = HuaweiChargerSensor(coordinator, "10047", is_diagnostic=True)

    assert sensor.name == "Register 10047"


def test_main_breaker_current_sensor_uses_ampere_unit():
    coordinator = DummyCoordinator({"20012": 40})
    sensor = HuaweiChargerSensor(coordinator, "20012", is_diagnostic=True)

    assert sensor.name == "Main Breaker Rated Current"
    assert sensor.native_value == 40
