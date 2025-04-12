from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfPower

from .const import DOMAIN, REGISTER_NAME_MAP, REG_FIXED_MAX_POWER, REG_DYNAMIC_POWER_LIMIT

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for reg_id in [REG_FIXED_MAX_POWER, REG_DYNAMIC_POWER_LIMIT]:
        entities.append(HuaweiChargerNumber(coordinator, reg_id))
    async_add_entities(entities)

class HuaweiChargerNumber(NumberEntity):
    def __init__(self, coordinator, reg_id):
        self.coordinator = coordinator
        self._reg_id = reg_id
        self._attr_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{reg_id}"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_native_min_value = 0.1
        self._attr_native_max_value = 22.0
        self._attr_native_step = 0.1
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def native_value(self):
        return float(self.coordinator.data.get(self._reg_id, 0))

    async def async_set_native_value(self, value: float):
        await self.hass.async_add_executor_job(self.coordinator.set_config_value, self._reg_id, value)
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        return self.coordinator.last_update_success