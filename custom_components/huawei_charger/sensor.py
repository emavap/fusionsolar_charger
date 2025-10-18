from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    UnitOfPower, UnitOfEnergy, UnitOfElectricCurrent, UnitOfElectricPotential,
    UnitOfFrequency, UnitOfTemperature, UnitOfTime, PERCENTAGE
)
import logging

from .const import DOMAIN, REGISTER_NAME_MAP

_LOGGER = logging.getLogger(__name__)

# Main sensors - visible by default (core charging information)
MAIN_SENSOR_REGISTERS = [
    "2101259",    # Phase A Voltage
    "2101260",    # Phase B Voltage  
    "2101261",    # Phase C Voltage
    "10008",      # Total Energy Charged
    "10009",      # Session Energy
    "10010",      # Session Duration
    "20012",      # Charging Status
    "20017",      # Plugged In
    "10003",      # Rated Power
    "2101271",    # Internal Temperature (more reliable than 20014)
]

# Diagnostic sensors - hidden by default (technical/configuration data)
DIAGNOSTIC_SENSOR_REGISTERS = [
    # Device identification
    "20011",      # Register 20011
    "10001",      # Register 10001
    "10002",      # Register 10002
    "20029",      # Register 20029
    "2101252",    # Register 2101252
    "2101251",    # Register 2101251
    "10007",      # Register 10007
    "10012",      # Register 10012
    
    # Status and error codes
    "20013",      # Register 20013
    "20015",      # Register 20015
    "20016",      # Register 20016
    "20014",      # Register 20014 (problematic sensor, moved to diagnostic)
    "15101",      # Register 15101
    
    # Network and IP configuration
    "538976516",  # Register 538976516
    "2101760",    # Register 2101760
    "2101763",    # Register 2101763
    "2101524",    # Register 2101524
    "2101526",    # Register 2101526
    "538976280",  # Register 538976280
    "538976281",  # Register 538976281
    "538976533",  # Register 538976533
    "538976534",  # Register 538976534
    
    # Power configuration
    "538976569",  # Register 538976569
    "538976570",  # Register 538976570
    "538976576",  # Register 538976576
    
    # System configuration
    "10047",      # Register 10047
    "538976288",  # Register 538976288
    "538976289",  # Register 538976289
    "538976308",  # Register 538976308
    "538976515",  # Register 538976515
    "538976517",  # Register 538976517
    "538976518",  # Register 538976518
    "538976519",  # Register 538976519
    "538976520",  # Register 538976520
    "538976558",  # Register 538976558
    "538976790",  # Register 538976790
    "538976800",  # Register 538976800
    
    # Reserved/Extended registers
    "10035",      # Register 10035
    "10034",      # Register 10034
    "10100",      # Register 10100
    "538976523",  # Register 538976523
    "538976564",  # Register 538976564
    "538976568",  # Register 538976568
    "539006279",  # Register 539006279
    "539006281",  # Register 539006281
    "539006282",  # Register 539006282
    "539006283",  # Register 539006283
    "539006284",  # Register 539006284
    "539006285",  # Register 539006285
    "539006286",  # Register 539006286
    "539006287",  # Register 539006287
    "539006288",  # Register 539006288
    "539006290",  # Register 539006290
    "539006291",  # Register 539006291
    "539006292",  # Register 539006292
    "539006293",  # Register 539006293
]

# Register configurations with units and device classes
REGISTER_CONFIG = {
    # Voltage related (confirmed in device data)
    "2101259": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
    "2101260": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
    "2101261": {"unit": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE, "state_class": SensorStateClass.MEASUREMENT},
    
    # Energy related (confirmed in device data)
    "10008": {"unit": UnitOfEnergy.KILO_WATT_HOUR, "device_class": SensorDeviceClass.ENERGY, "state_class": SensorStateClass.TOTAL_INCREASING},
    "10009": {"unit": UnitOfEnergy.KILO_WATT_HOUR, "device_class": SensorDeviceClass.ENERGY, "state_class": SensorStateClass.TOTAL},
    
    # Time related (confirmed in device data)
    "10010": {"unit": UnitOfTime.MINUTES, "device_class": SensorDeviceClass.DURATION, "state_class": SensorStateClass.TOTAL},
    
    # Temperature (confirmed in device data)
    "20014": {"unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE, "state_class": SensorStateClass.MEASUREMENT},
    "2101271": {"unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE, "state_class": SensorStateClass.MEASUREMENT},
    "15101": {"unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE, "state_class": SensorStateClass.MEASUREMENT},
    
    # Power related (confirmed in device data)
    "10003": {"unit": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER},
    "538976569": {"unit": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER},
    "538976570": {"unit": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER},
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    # Add main sensors (visible by default)
    for reg_id in MAIN_SENSOR_REGISTERS:
        entities.append(HuaweiChargerSensor(coordinator, reg_id, is_diagnostic=False))
    
    # Add diagnostic sensors (hidden by default)
    for reg_id in DIAGNOSTIC_SENSOR_REGISTERS:
        entities.append(HuaweiChargerSensor(coordinator, reg_id, is_diagnostic=True))
    
    async_add_entities(entities)

class HuaweiChargerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, reg_id, is_diagnostic=False):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._reg_id = reg_id
        self._is_diagnostic = is_diagnostic
        # Use register numbers for diagnostic sensors, mapped names for main sensors
        if is_diagnostic:
            self._attr_name = f"Register {reg_id}"
        else:
            self._attr_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
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
        raw_value = self.coordinator.data.get(self._reg_id)
        
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
            
            # For temperature values, ensure proper formatting
            if self._reg_id in ["20014", "2101271", "15101"]:
                if isinstance(raw_value, (int, float)):
                    temp_value = float(raw_value)
                    
                    # Register 20014 appears to have issues, apply temperature offset if available
                    if self._reg_id == "20014":
                        offset_value = self.coordinator.data.get("15101")
                        if offset_value is not None:
                            try:
                                offset = float(offset_value)
                                temp_value = temp_value - offset  # Apply temperature offset correction
                                _LOGGER.debug("Temperature %s: raw=%s, offset=%s, corrected=%s", 
                                            self._reg_id, raw_value, offset, temp_value)
                            except (ValueError, TypeError):
                                _LOGGER.warning("Invalid temperature offset value: %s", offset_value)
                    
                    return round(temp_value, 1)
                    
            # For energy values, ensure proper formatting
            if self._reg_id in ["10008", "10009"]:
                if isinstance(raw_value, (int, float)):
                    return round(float(raw_value), 3)
                    
            # For voltage values, ensure proper formatting
            if self._reg_id in ["2101259", "2101260", "2101261"]:
                if isinstance(raw_value, (int, float)):
                    return round(float(raw_value), 1)
                    
            # For time values (session duration in minutes)
            if self._reg_id == "10010":
                if isinstance(raw_value, (int, float)):
                    return int(raw_value)
                    
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
            _LOGGER.warning("Could not convert value for register %s: %s", self._reg_id, raw_value)
            return str(raw_value)

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data.get(self._reg_id) is not None

    @property
    def extra_state_attributes(self):
        return {
            "register_id": self._reg_id,
            "raw_value": self.coordinator.data.get(self._reg_id)
        }
