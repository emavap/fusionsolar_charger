from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import callback
from homeassistant.const import (
    UnitOfPower, UnitOfEnergy, UnitOfElectricCurrent, UnitOfElectricPotential,
    UnitOfFrequency, UnitOfTemperature, UnitOfTime, PERCENTAGE
)
import logging

from .const import DOMAIN, REGISTER_NAME_MAP, SENSITIVE_REGISTERS, WRITABLE_REGISTERS

_LOGGER = logging.getLogger(__name__)

DEBUG_SENSOR_TYPES = {
    "update": {
        "name": "Debug Update Status",
        "key": "last_update_status",
    },
    "write": {
        "name": "Debug Write Status",
        "key": "last_write_status",
    },
}

# Main sensors - visible by default (core charging information)
MAIN_SENSOR_REGISTERS = [
    "device_status",  # Charger status from wallbox-info
    "20017",      # Plugged In
    "10003",      # Rated Charging Power
    "10008",      # Total Energy Charged
    "10009",      # Session Energy
    "10010",      # Session Duration
]

# Register configurations with units and device classes
REGISTER_CONFIG = {
    # Energy related
    "10008": {"unit": UnitOfEnergy.KILO_WATT_HOUR, "device_class": SensorDeviceClass.ENERGY, "state_class": SensorStateClass.TOTAL_INCREASING},
    "10009": {"unit": UnitOfEnergy.KILO_WATT_HOUR, "device_class": SensorDeviceClass.ENERGY},
    # Current related
    "20012": {"unit": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT, "state_class": SensorStateClass.MEASUREMENT},
    # Power related
    "10003": {"unit": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER},
    # Timing related
    "10010": {"unit": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
    "539006290": {"unit": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
    # Voltage related
    "2101259": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
    "2101260": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
    "2101261": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
}


def _register_sort_key(reg_id):
    reg_id = str(reg_id)
    return (0, int(reg_id)) if reg_id.isdigit() else (1, reg_id)


def _sensor_unique_id(entry_id, reg_id):
    return f"{entry_id}_sensor_{reg_id}"


def _active_sensor_registers(data, config_signal_values=None, existing_register_ids=None):
    available_registers = {str(reg_id) for reg_id in (data or {})}
    available_registers.update(str(reg_id) for reg_id in (config_signal_values or {}))
    available_registers.update(str(reg_id) for reg_id in (existing_register_ids or set()))

    available_registers.difference_update(WRITABLE_REGISTERS)
    available_registers.difference_update(SENSITIVE_REGISTERS)

    active_main = [reg_id for reg_id in MAIN_SENSOR_REGISTERS if reg_id in available_registers]
    active_diagnostic = sorted(
        available_registers.difference(active_main),
        key=_register_sort_key,
    )
    return active_main, active_diagnostic


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    registry = er.async_get(hass)
    current_data = getattr(coordinator, "data", None) or getattr(coordinator, "param_values", {})

    active_main, active_diagnostic = _active_sensor_registers(
        current_data,
        coordinator.config_signal_values,
    )

    for reg_id in active_main:
        entities.append(HuaweiChargerSensor(coordinator, reg_id, is_diagnostic=False))

    for reg_id in active_diagnostic:
        entities.append(HuaweiChargerSensor(coordinator, reg_id, is_diagnostic=True))

    for debug_type in DEBUG_SENSOR_TYPES:
        entities.append(HuaweiChargerDebugSensor(coordinator, debug_type))

    active_sensor_ids = set(active_main + active_diagnostic)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.domain != "sensor" or not registry_entry.unique_id:
            continue

        if registry_entry.unique_id in {
            _sensor_unique_id(entry.entry_id, sensitive_reg_id)
            for sensitive_reg_id in SENSITIVE_REGISTERS
        }:
            registry.async_remove(registry_entry.entity_id)
            continue

        sensor_prefix = f"{entry.entry_id}_sensor_"
        if not registry_entry.unique_id.startswith(sensor_prefix):
            continue

        reg_id = registry_entry.unique_id[len(sensor_prefix):]
        if reg_id not in active_sensor_ids:
            registry.async_remove(registry_entry.entity_id)

    async_add_entities(entities)

    known_register_ids = set(active_main + active_diagnostic)

    @callback
    def _async_add_new_sensors():
        nonlocal known_register_ids
        updated_data = getattr(coordinator, "data", None) or getattr(coordinator, "param_values", {})

        updated_main, updated_diagnostic = _active_sensor_registers(
            updated_data,
            coordinator.config_signal_values,
            known_register_ids,
        )
        updated_register_ids = set(updated_main + updated_diagnostic)
        new_register_ids = updated_register_ids.difference(known_register_ids)
        if not new_register_ids:
            return

        new_entities = [
            HuaweiChargerSensor(
                coordinator,
                reg_id,
                is_diagnostic=reg_id not in MAIN_SENSOR_REGISTERS,
            )
            for reg_id in sorted(new_register_ids, key=_register_sort_key)
        ]
        known_register_ids.update(new_register_ids)
        async_add_entities(new_entities)

    remove_listener = coordinator.async_add_listener(_async_add_new_sensors)
    if hasattr(entry, "async_on_unload"):
        entry.async_on_unload(remove_listener)

class HuaweiChargerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, reg_id, is_diagnostic=False):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._reg_id = reg_id
        self._is_diagnostic = is_diagnostic
        mapped_name = REGISTER_NAME_MAP.get(reg_id)
        self._attr_name = mapped_name or f"Register {reg_id}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_sensor_{reg_id}"
        
        # Set entity category for diagnostic sensors
        if is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # Set up device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }
        
        # Configure sensor attributes based on register type
        config = REGISTER_CONFIG.get(reg_id, {})
        if "unit" in config:
            self._attr_native_unit_of_measurement = config["unit"]
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
        if "state_class" in config:
            self._attr_state_class = config["state_class"]

    @property
    def native_value(self):
        if self._reg_id in SENSITIVE_REGISTERS:
            return None

        raw_value = self.coordinator.get_register_value(self._reg_id)
        
        # Return None if no data available
        if raw_value is None:
            return None
            
        # Convert values if needed
        try:
            # For power values, ensure they're in kW
            if self._reg_id in ["10003", "538976569", "538976570"] and isinstance(raw_value, (int, float)):
                # Convert W to kW if the value seems to be in watts
                if raw_value > 100:  # Assume values > 100 are in watts
                    return raw_value / 1000
                return float(raw_value)
            
            # For energy values, ensure proper formatting
            if self._reg_id in ["10008", "10009"]:
                if isinstance(raw_value, (int, float)):
                    return round(float(raw_value), 3)

            # For current/time values, ensure proper formatting
            if self._reg_id in ["10010", "20012", "539006290"] and isinstance(raw_value, (int, float)):
                return int(raw_value) if float(raw_value).is_integer() else round(float(raw_value), 1)

            if self._reg_id in ["2101259", "2101260", "2101261"] and isinstance(raw_value, (int, float)):
                return round(float(raw_value), 1)
                    
            # Special handling for Device Info register (2101251)
            if self._reg_id == "2101251":
                if isinstance(raw_value, str):
                    # Extract key information from the device info
                    lines = raw_value.split('\n')
                    extracted = {}
                    for line in lines:
                        line = line.strip()
                        if not line or '=' not in line:
                            continue
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip()
                        if key in ("BoardType", "Model", "VendorName") and value:
                            extracted[key] = value

                    if extracted:
                        ordered_keys = ["BoardType", "Model", "VendorName"]
                        key_info = [extracted[key] for key in ordered_keys if key in extracted]
                        if key_info:
                            return ' - '.join(key_info)
                    # Fallback: just return first meaningful line
                    for line in lines:
                        stripped_line = line.strip()
                        if stripped_line and not stripped_line.startswith('/$') and '=' in stripped_line:
                            return stripped_line[:200]  # Limit to 200 chars
                    return "Device Info Available"
                return str(raw_value)[:200]  # Fallback truncation
                    
            # Default: pass through native numeric values
            if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, bool):
                return raw_value
            
            # Ensure string values don't exceed 255 characters
            str_value = str(raw_value)
            if len(str_value) > 255:
                return str_value[:252] + "..."
            return str_value
            
        except (ValueError, TypeError):
            self._log_warning("Could not convert value for register %s: %s", self._reg_id, raw_value)
            return str(raw_value)

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        if self._reg_id in SENSITIVE_REGISTERS:
            return False
        return self.coordinator.get_register_value(self._reg_id) is not None

    @property
    def extra_state_attributes(self):
        return {
            "register_id": self._reg_id,
            "raw_value": (
                "***"
                if self._reg_id in SENSITIVE_REGISTERS
                else self.coordinator.get_register_value(self._reg_id)
            ),
            "stale": not self.coordinator.last_update_success,
        }

    def _log_warning(self, message, *args):
        if getattr(self.coordinator, "enable_logging", True):
            _LOGGER.warning(message, *args)


class HuaweiChargerDebugSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, debug_type):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._debug_type = debug_type
        config = DEBUG_SENSOR_TYPES[debug_type]
        self._state_key = config["key"]
        self._attr_name = config["name"]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_debug_{debug_type}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def native_value(self):
        return self.coordinator.debug_data.get(self._state_key)

    @property
    def available(self):
        return True

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        debug_data = self.coordinator.debug_data
        if self._debug_type == "update":
            return {
                "last_update_error": debug_data.get("last_update_error"),
                "last_update_at": debug_data.get("last_update_at"),
                "last_update_duration_ms": debug_data.get("last_update_duration_ms"),
                "last_update_response_excerpt": debug_data.get("last_update_response_excerpt"),
                "last_register_count": debug_data.get("last_register_count"),
                "writable_registers_available": debug_data.get("writable_registers_available"),
                "missing_writable_registers": debug_data.get("missing_writable_registers"),
                "available_registers": debug_data.get("available_registers"),
            }

        return {
            "last_write_param_id": debug_data.get("last_write_param_id"),
            "last_write_value": debug_data.get("last_write_value"),
            "last_write_error": debug_data.get("last_write_error"),
            "last_write_at": debug_data.get("last_write_at"),
            "last_write_duration_ms": debug_data.get("last_write_duration_ms"),
            "last_write_attempts": debug_data.get("last_write_attempts"),
            "last_write_response_excerpt": debug_data.get("last_write_response_excerpt"),
        }
