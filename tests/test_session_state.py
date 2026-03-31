from types import SimpleNamespace

from custom_components.huawei_charger.session_state import (
    charging_state,
    is_charging_state,
    is_connected_state,
    vehicle_connected_state,
)


class DummyCoordinator:
    def __init__(self, values):
        self._values = values
        self.entry = SimpleNamespace(entry_id="entry-1")

    def get_register_value(self, reg_id):
        return self._values.get(reg_id)


def test_is_connected_state_handles_common_values():
    assert is_connected_state(True) is True
    assert is_connected_state(False) is False
    assert is_connected_state(1) is True
    assert is_connected_state(0) is False
    assert is_connected_state("ready") is True
    assert is_connected_state("plugged") is True
    assert is_connected_state("4") is True
    assert is_connected_state("10") is True
    assert is_connected_state("false") is False
    assert is_connected_state("idle") is False
    assert is_connected_state("98") is False
    assert is_connected_state("mystery") is None


def test_vehicle_connected_prefers_plugged_register():
    coordinator = DummyCoordinator({"20017": "1", "device_status": "0"})

    state, source = vehicle_connected_state(coordinator)

    assert state is True
    assert source == "20017"


def test_vehicle_connected_falls_back_to_device_status():
    coordinator = DummyCoordinator({"device_status": "2"})

    state, source = vehicle_connected_state(coordinator)

    assert state is True
    assert source == "device_status"


def test_vehicle_connected_returns_unknown_when_no_signal_exists():
    coordinator = DummyCoordinator({})

    state, source = vehicle_connected_state(coordinator)

    assert state is None
    assert source is None


def test_is_charging_state_handles_common_values():
    assert is_charging_state(True) is True
    assert is_charging_state(False) is False
    assert is_charging_state(1) is True
    assert is_charging_state(0) is False
    assert is_charging_state("charging") is True
    assert is_charging_state("3") is True
    assert is_charging_state("11") is True
    assert is_charging_state("ready") is False
    assert is_charging_state("4") is False
    assert is_charging_state("8") is False
    assert is_charging_state("plugged") is False
    assert is_charging_state("mystery") is None


def test_charging_state_prefers_device_status():
    coordinator = DummyCoordinator({"device_status": "3", "charge_store": "0"})

    state, source = charging_state(coordinator)

    assert state is True
    assert source == "device_status"


def test_charging_state_falls_back_to_charge_store():
    coordinator = DummyCoordinator({"charge_store": "charging"})

    state, source = charging_state(coordinator)

    assert state is True
    assert source == "charge_store"
