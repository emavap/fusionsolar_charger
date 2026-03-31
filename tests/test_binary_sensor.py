from types import SimpleNamespace

from custom_components.huawei_charger.binary_sensor import (
    _is_connected_state,
    _vehicle_connected_state,
)


class DummyCoordinator:
    def __init__(self, values):
        self._values = values
        self.entry = SimpleNamespace(entry_id="entry-1")

    def get_register_value(self, reg_id):
        return self._values.get(reg_id)


def test_is_connected_state_handles_common_values():
    assert _is_connected_state(True) is True
    assert _is_connected_state(False) is False
    assert _is_connected_state(1) is True
    assert _is_connected_state(0) is False
    assert _is_connected_state("ready") is True
    assert _is_connected_state("plugged") is True
    assert _is_connected_state("false") is False
    assert _is_connected_state("idle") is False
    assert _is_connected_state("mystery") is None


def test_vehicle_connected_prefers_plugged_register():
    coordinator = DummyCoordinator({"20017": "1", "device_status": "0"})

    state, source = _vehicle_connected_state(coordinator)

    assert state is True
    assert source == "20017"


def test_vehicle_connected_falls_back_to_device_status():
    coordinator = DummyCoordinator({"device_status": "2"})

    state, source = _vehicle_connected_state(coordinator)

    assert state is True
    assert source == "device_status"


def test_vehicle_connected_returns_unknown_when_no_signal_exists():
    coordinator = DummyCoordinator({})

    state, source = _vehicle_connected_state(coordinator)

    assert state is None
    assert source is None
