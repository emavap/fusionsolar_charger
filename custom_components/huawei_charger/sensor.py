from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfPower, UnitOfEnergy, UnitOfElectricCurrent, UnitOfElectricPotential,
    UnitOfFrequency, UnitOfTemperature, UnitOfTime, PERCENTAGE
)
import logging

from .const import DOMAIN, REGISTER_NAME_MAP

_LOGGER = logging.getLogger(__name__)

INTERESTING_SENSOR_REGISTERS = [
    # Core device information (confirmed in device data)
    "538976516", "2101259", "20011", "10008", "10001", "20013", "20017", "20029",
    # Voltage and power data (confirmed in device data)
    "2101260", "2101261", "10009", "10010", "20012", "20014", "20015", "20016",
    # Device information registers (confirmed in device data)
    "10002", "10003", "10007", "10012", "10047", "10035", "10034", "10100",
    "15101", "2101251", "2101252", "2101271",
    # Network status registers (confirmed in device data)
    "2101524", "2101526", "2101760", "2101763",
    # Configuration registers (confirmed in device data)
    "538976280", "538976281", "538976288", "538976289", "538976308",
    "538976515", "538976517", "538976518", "538976519", "538976520",
    "538976523", "538976533", "538976534", "538976558", "538976564",
    "538976568", "538976569", "538976570", "538976576", "538976790", "538976800",
    # Extended status registers (confirmed in device data)
    "539006279", "539006281", "539006282", "539006283", "539006284",
    "539006285", "539006286", "539006287", "539006288", "539006290",
    "539006291", "539006292", "539006293"
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
    for reg_id in INTERESTING_SENSOR_REGISTERS:
        entities.append(HuaweiChargerSensor(coordinator, reg_id))
    async_add_entities(entities)

class HuaweiChargerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, reg_id):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._reg_id = reg_id
        base_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
        self._attr_name = f"Huawei Charger {base_name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_sensor_{reg_id}"
        
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
                    return round(float(raw_value), 1)
                    
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
                    key_info = []
                    for line in lines:
                        if 'BoardType=' in line:
                            key_info.append(line.split('=')[1])
                        elif 'Model=' in line:
                            key_info.append(line.split('=')[1])
                        elif 'VendorName=' in line:
                            key_info.append(line.split('=')[1])
                    if key_info:
                        return ' - '.join(key_info)
                    # Fallback: just return first meaningful line
                    for line in lines:
                        if line.strip() and not line.startswith('/$') and '=' in line:
                            return line.strip()[:200]  # Limit to 200 chars
                    return "Device Info Available"
                return str(raw_value)[:200]  # Fallback truncation
                    
            # Default: return string values as-is, numeric as float
            if isinstance(raw_value, (int, float)):
                return float(raw_value)
            
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
