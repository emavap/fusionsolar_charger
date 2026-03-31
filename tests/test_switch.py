import asyncio
from types import SimpleNamespace

from custom_components.huawei_charger.switch import HuaweiChargerChargingSwitch


class DummyCoordinator:
    def __init__(self, values):
        self._values = values
        self.entry = SimpleNamespace(entry_id="entry-1")
        self.wallbox_dn_id = "wallbox-1"
        self.wallbox_dn = "NE=1"
        self.data = values
        self.refresh_calls = 0
        self.start_calls = 0
        self.stop_calls = 0

    def get_register_value(self, reg_id):
        return self._values.get(reg_id)

    def start_charge(self):
        self.start_calls += 1
        return True

    def stop_charge(self):
        self.stop_calls += 1
        return True

    async def async_request_refresh(self):
        self.refresh_calls += 1


class DummyHass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


def test_switch_uses_session_status_to_report_on_state():
    coordinator = DummyCoordinator({"device_status": "3"})
    entity = HuaweiChargerChargingSwitch(coordinator)

    assert entity.available is True
    assert entity.is_on is True
    assert entity.extra_state_attributes["control_path"].startswith("FusionSolar cloud")


def test_switch_reports_off_when_ready_but_not_charging():
    coordinator = DummyCoordinator({"device_status": "2"})
    entity = HuaweiChargerChargingSwitch(coordinator)

    assert entity.is_on is False


def test_switch_turn_on_calls_start_charge():
    coordinator = DummyCoordinator({"device_status": "2"})
    entity = HuaweiChargerChargingSwitch(coordinator)
    entity.hass = DummyHass()

    asyncio.run(entity.async_turn_on())

    assert coordinator.start_calls == 1
    assert coordinator.refresh_calls == 1


def test_switch_turn_off_calls_stop_charge():
    coordinator = DummyCoordinator({"device_status": "3"})
    entity = HuaweiChargerChargingSwitch(coordinator)
    entity.hass = DummyHass()

    asyncio.run(entity.async_turn_off())

    assert coordinator.stop_calls == 1
    assert coordinator.refresh_calls == 1
