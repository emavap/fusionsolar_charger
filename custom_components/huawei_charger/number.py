from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower
import asyncio
import logging

from .const import DOMAIN, REGISTER_NAME_MAP, REG_FIXED_MAX_POWER, REG_DYNAMIC_POWER_LIMIT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for reg_id in [REG_FIXED_MAX_POWER, REG_DYNAMIC_POWER_LIMIT]:
        entities.append(HuaweiChargerNumber(coordinator, reg_id))
    async_add_entities(entities)

class HuaweiChargerNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, reg_id):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._reg_id = reg_id
        base_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
        self._attr_name = f"Huawei Charger {base_name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{reg_id}"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        # Set dynamic limits based on device capabilities
        self._set_power_limits()
        # Set step size based on power range (0.1 kW for smaller chargers, 0.2 kW for larger)
        self._attr_native_step = 0.1 if self._attr_native_max_value <= 3.7 else 0.2
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }
    
    def _set_power_limits(self):
        """Set power limits based on device capabilities from registers."""
        # Default fallback values
        min_power = 1.6
        max_power = 7.4
        
        try:
            # Try to get limits from device registers
            if self.coordinator.data:
                # Min power from register 538976569
                if "538976569" in self.coordinator.data:
                    device_min = float(self.coordinator.data["538976569"])
                    if device_min > 0:
                        min_power = device_min
                        
                # Max power from multiple possible registers
                max_candidates = ["538976570", "10003"]  # Max Power, Rated Power
                for reg_id in max_candidates:
                    if reg_id in self.coordinator.data:
                        device_max = float(self.coordinator.data[reg_id])
                        if device_max > min_power:
                            max_power = device_max
                            break
                            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not parse power limits from device, using defaults: %s", err)
            
        self._attr_native_min_value = min_power
        self._attr_native_max_value = max_power
        _LOGGER.info("Set power limits for %s: min=%.1f kW, max=%.1f kW", 
                    self._attr_name, min_power, max_power)

    @property
    def native_value(self):
        raw_value = self.coordinator.data.get(self._reg_id)
        if raw_value is None:
            return None
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            _LOGGER.warning("Could not convert value for register %s: %s", self._reg_id, raw_value)
            return 0.0

    async def async_set_native_value(self, value: float):
        if not isinstance(value, (int, float)) or value < self._attr_native_min_value or value > self._attr_native_max_value:
            _LOGGER.error("Invalid value %s for register %s (must be between %s and %s)", 
                         value, self._reg_id, self._attr_native_min_value, self._attr_native_max_value)
            return
            
        success = await self.hass.async_add_executor_job(self.coordinator.set_config_value, self._reg_id, value)
        if success:
            await asyncio.sleep(10)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set value %s for register %s", value, self._reg_id)

    @property
    def available(self):
        return self.coordinator.last_update_success
