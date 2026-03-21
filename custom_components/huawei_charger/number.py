from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower
import asyncio
import logging
import time

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
        self._attr_name = base_name
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
        
        # EEPROM protection: debouncing and rate limiting
        self._pending_value = None
        self._pending_task = None
        self._last_write_time = 0
        self._last_set_value = None
        self._debounce_delay = 5.0  # seconds
        self._min_write_interval = 30.0  # seconds minimum between writes
    
    def _set_power_limits(self):
        """Set power limits based on device capabilities from registers."""
        # Default fallback values
        min_power = 1.6
        max_power = 7.4
        
        try:
            signal_details = getattr(self.coordinator, "config_signal_details", {}).get(self._reg_id, {})
            signal_min = signal_details.get("min")
            signal_max = signal_details.get("max")
            if signal_min is not None:
                parsed_min = float(signal_min)
                if parsed_min > 0:
                    min_power = parsed_min
            if signal_max is not None:
                parsed_max = float(signal_max)
                if parsed_max > min_power:
                    max_power = parsed_max

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
            self._log_warning("Could not parse power limits from device, using defaults: %s", err)
            
        self._attr_native_min_value = min_power
        self._attr_native_max_value = max_power
        self._log_warning(
            "Set power limits for %s: min=%.1f kW, max=%.1f kW",
            self._attr_name,
            min_power,
            max_power,
        )

    def _handle_coordinator_update(self):
        self._set_power_limits()
        self._attr_native_step = 0.1 if self._attr_native_max_value <= 3.7 else 0.2
        super()._handle_coordinator_update()

    @property
    def native_value(self):
        raw_value = self.coordinator.get_register_value(self._reg_id)
        if raw_value is None:
            return None
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            self._log_warning("Could not convert value for register %s: %s", self._reg_id, raw_value)
            return 0.0

    async def async_set_native_value(self, value: float):
        if not isinstance(value, (int, float)) or value < self._attr_native_min_value or value > self._attr_native_max_value:
            _LOGGER.error("Invalid value %s for register %s (must be between %s and %s)", 
                         value, self._reg_id, self._attr_native_min_value, self._attr_native_max_value)
            return
        
        # Skip if value hasn't changed (avoid redundant writes)
        if self._last_set_value is not None and abs(value - self._last_set_value) < 0.01:
            self._log_warning(
                "Skipping redundant write for register %s: value unchanged (%.2f)",
                self._reg_id,
                value,
            )
            return
        
        # Cancel any pending write task
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
            self._log_warning("Cancelled pending write task for register %s", self._reg_id)
        
        # Store the pending value
        self._pending_value = value
        
        # Start debounced write task
        self._pending_task = asyncio.create_task(self._debounced_write())
    
    async def _debounced_write(self):
        """Execute a debounced write with rate limiting to protect EEPROM."""
        try:
            # Wait for debounce period
            await asyncio.sleep(self._debounce_delay)
            
            # Check if we need to respect minimum write interval
            current_time = time.time()
            time_since_last_write = current_time - self._last_write_time
            
            if time_since_last_write < self._min_write_interval:
                remaining_wait = self._min_write_interval - time_since_last_write
                self._log_warning(
                    "Rate limiting: waiting %.1f seconds before writing register %s",
                    remaining_wait,
                    self._reg_id,
                )
                await asyncio.sleep(remaining_wait)
            
            # Perform the actual write
            value = self._pending_value
            if value is None:
                return
                
            self._log_warning("Writing debounced value %.2f to register %s", value, self._reg_id)
            success = await self.hass.async_add_executor_job(
                self.coordinator.set_config_value, self._reg_id, value
            )
            
            if success:
                self._last_write_time = time.time()
                self._last_set_value = value
                self._pending_value = None
                
                # Wait before refresh to allow device to process the change
                await asyncio.sleep(10)
                await self.coordinator.async_request_refresh()
                
                self._log_warning(
                    "Successfully set register %s to %.2f with EEPROM protection",
                    self._reg_id,
                    value,
                )
            else:
                _LOGGER.error("Failed to set value %.2f for register %s", value, self._reg_id)
                
        except asyncio.CancelledError:
            self._log_warning("Debounced write cancelled for register %s", self._reg_id)
        except Exception as err:
            _LOGGER.error("Error in debounced write for register %s: %s", self._reg_id, err)

    @property
    def available(self):
        return self.coordinator.get_register_value(self._reg_id) is not None

    def _log_warning(self, message, *args):
        if getattr(self.coordinator, "enable_logging", True):
            _LOGGER.warning(message, *args)
