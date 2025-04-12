from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, REGISTER_NAME_MAP

WRITABLE_REGISTERS = {
    "538976598": "Fixed Max Charging Power",  # kW
    "20001": "Dynamic Power Limit"            # kW
}

def get_model_max_power(model: str) -> float:
    if "22KS" in model:
        return 22.0
    if "7KS" in model:
        return 7.4
    return 7.4  # Default fallback

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    param_values = coordinator.data.get("paramValues", {})
    model = param_values.get("10007", "")
    max_power = get_model_max_power(model)

    current_fixed = float(param_values.get("538976598", 0))
    current_dynamic = float(param_values.get("20001", 0))

    entities = [
        HuaweiChargerNumber(coordinator, "538976598", "Fixed Max Charging Power", current_fixed, max_power, current_dynamic),
        HuaweiChargerNumber(coordinator, "20001", "Dynamic Power Limit", current_dynamic, current_fixed, max_power)
    ]

    async_add_entities(entities)

class HuaweiChargerNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, register, name, current_value, related_value, max_power):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{register}"
        self._attr_name = name
        self._register = register
        self._attr_native_value = current_value
        self._attr_native_unit_of_measurement = "kW"
        self._attr_native_min_value = 0.0
        self._max_power = max_power
        self._related_value = related_value
        self._attr_native_step = 0.1

    @property
    def native_max_value(self):
        if self._register == "20001":  # Dynamic Power Limit can't exceed Fixed Max
            return min(self._related_value, self._max_power)
        elif self._register == "538976598":  # Fixed Max must be ≥ Dynamic
            return self._max_power
        return self._max_power

    @property
    def native_min_value(self):
        if self._register == "538976598":  # Fixed Max must be ≥ Dynamic
            return self._related_value
        return 0.0

    async def async_set_native_value(self, value: float):
        value = max(min(value, self.native_max_value), self.native_min_value)
        if value != self._attr_native_value:
            await self.coordinator.set_register(self._register, value)
        self._attr_native_value = value
        self.async_write_ha_state()