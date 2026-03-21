import asyncio
import itertools
from types import SimpleNamespace

import pytest

from custom_components.huawei_charger.const import (
    REG_DYNAMIC_POWER_LIMIT,
    REG_FIXED_MAX_POWER,
)
from custom_components.huawei_charger.number import HuaweiChargerNumber


class DummyCoordinator:
    def __init__(self, data=None, last_update_success=True):
        self.data = data or {}
        self.entry = SimpleNamespace(entry_id="entry")
        self.last_update_success = last_update_success
        self.set_calls = []
        self.refresh_calls = 0
        self.config_signal_details = {}
        self.config_signal_values = {}

    def set_config_value(self, reg_id, value):
        self.set_calls.append((reg_id, value))
        return True

    def get_register_value(self, reg_id):
        reg_id = str(reg_id)
        if reg_id in self.data:
            return self.data[reg_id]
        return self.config_signal_values.get(reg_id)

    async def async_request_refresh(self):
        self.refresh_calls += 1


class FakeHass:
    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


def test_number_limits_from_device_data():
    coordinator = DummyCoordinator({"538976569": 1.8, "538976570": 7.4})
    number = HuaweiChargerNumber(coordinator, REG_FIXED_MAX_POWER)

    assert number.native_min_value == pytest.approx(1.8)
    assert number.native_max_value == pytest.approx(7.4)
    assert number.native_step == 0.2


def test_number_limits_fallback():
    coordinator = DummyCoordinator()
    number = HuaweiChargerNumber(coordinator, REG_DYNAMIC_POWER_LIMIT)

    assert number.native_min_value == pytest.approx(1.6)
    assert number.native_max_value == pytest.approx(7.4)
    assert number.native_step == 0.2


def test_number_limits_from_config_signal_metadata():
    coordinator = DummyCoordinator()
    coordinator.config_signal_details = {
        REG_DYNAMIC_POWER_LIMIT: {
            "min": "1.4",
            "max": "7.4",
        }
    }
    number = HuaweiChargerNumber(coordinator, REG_DYNAMIC_POWER_LIMIT)

    assert number.native_min_value == pytest.approx(1.4)
    assert number.native_max_value == pytest.approx(7.4)


def test_number_native_value_handles_invalid():
    coordinator = DummyCoordinator()
    coordinator.config_signal_values = {REG_FIXED_MAX_POWER: "not-a-number"}
    number = HuaweiChargerNumber(coordinator, REG_FIXED_MAX_POWER)

    assert number.native_value == 0.0


def test_async_set_native_value_debounced(monkeypatch):
    coordinator = DummyCoordinator()
    coordinator.config_signal_values = {REG_FIXED_MAX_POWER: 2.0}
    number = HuaweiChargerNumber(coordinator, REG_FIXED_MAX_POWER)
    number.hass = FakeHass()

    real_sleep = asyncio.sleep
    sleep_calls = []

    async def fast_sleep(delay):
        sleep_calls.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(
        "custom_components.huawei_charger.number.asyncio.sleep", fast_sleep
    )

    times = itertools.chain([100.0, 140.0, 200.0], itertools.repeat(200.0))
    monkeypatch.setattr(
        "custom_components.huawei_charger.number.time.time", lambda: next(times)
    )

    async def run():
        await number.async_set_native_value(number.native_min_value - 0.5)
        assert coordinator.set_calls == []

        await number.async_set_native_value(3.0)
        assert number._pending_task is not None
        await number._pending_task

        assert coordinator.set_calls == [(REG_FIXED_MAX_POWER, 3.0)]
        assert coordinator.refresh_calls == 1
        assert number._pending_value is None
        assert number._last_set_value == pytest.approx(3.0)
        assert sleep_calls == [5.0, 10]

        await number.async_set_native_value(3.0)
        assert coordinator.set_calls == [(REG_FIXED_MAX_POWER, 3.0)]

    asyncio.run(run())


def test_number_stays_available_with_cached_value():
    coordinator = DummyCoordinator(last_update_success=False)
    coordinator.config_signal_values = {REG_FIXED_MAX_POWER: 7.4}
    number = HuaweiChargerNumber(coordinator, REG_FIXED_MAX_POWER)

    assert number.available is True
