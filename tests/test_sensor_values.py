from types import SimpleNamespace

import pytest

from custom_components.huawei_charger.sensor import HuaweiChargerSensor


class DummyCoordinator:
    """Minimal coordinator stub for unit tests."""

    def __init__(self, data, entry_id="test_entry", last_update_success=True):
        self.data = data
        self.entry = SimpleNamespace(entry_id=entry_id)
        self.last_update_success = last_update_success

    def async_add_listener(self, update_callback):
        # CoordinatorEntity expects a callable that removes the listener
        return lambda: None


def test_power_sensor_converts_watts_to_kw():
    coordinator = DummyCoordinator({"538976570": 7400})
    sensor = HuaweiChargerSensor(coordinator, "538976570")

    assert sensor.native_value == pytest.approx(7.4)


def test_voltage_sensor_rounds_to_one_decimal():
    coordinator = DummyCoordinator({"2101259": 231})
    sensor = HuaweiChargerSensor(coordinator, "2101259")

    assert sensor.native_value == pytest.approx(231.0)


def test_temperature_sensor_applies_offset():
    coordinator = DummyCoordinator({"20014": 25.5, "15101": -2})
    sensor = HuaweiChargerSensor(coordinator, "20014", is_diagnostic=True)

    assert sensor.native_value == pytest.approx(27.5, rel=1e-3)


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


def test_sensor_extra_state_attributes():
    coordinator = DummyCoordinator({"538976598": 7.4})
    sensor = HuaweiChargerSensor(coordinator, "538976598")

    attrs = sensor.extra_state_attributes
    assert attrs["register_id"] == "538976598"
    assert attrs["raw_value"] == 7.4
