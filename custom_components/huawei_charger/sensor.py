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
    "20014",      # Temperature
]

# Diagnostic sensors - hidden by default (technical/configuration data)
DIAGNOSTIC_SENSOR_REGISTERS = [
    # Device identification
    "20011",      # Device Name
    "10001",      # Software Version
    "10002",      # Hardware Version
    "20029",      # Device Serial Number
    "2101252",    # Serial Number Alt
    "2101251",    # Device Info
    "10007",      # Device Type
    "10012",      # Device Model
    
    # Status and error codes
    "20013",      # Lock Status
    "20015",      # Error Code
    "20016",      # Warning Code
    "2101271",    # Internal Temperature
    "15101",      # Temperature Offset
    
    # Network and IP configuration
    "538976516",  # Device IP
    "2101760",    # Network IP
    "2101763",    # Network Port
    "2101524",    # Network Status 1
    "2101526",    # Network Status 2
    "538976280",  # Management IP
    "538976281",  # Server Address
    "538976533",  # Local IP
    "538976534",  # HTTP Port
    
    # Power configuration
    "538976569",  # Min Power
    "538976570",  # Max Power
    "538976576",  # Power Mode
    
    # System configuration
    "10047",      # Phase Count
    "538976288",  # Port Number
    "538976289",  # Protocol Version
    "538976308",  # Device ID
    "538976515",  # DHCP Enable
    "538976517",  # Subnet Mask
    "538976518",  # Gateway
    "538976519",  # DNS Primary
    "538976520",  # DNS Secondary
    "538976558",  # SSL Enable
    "538976790",  # System Status
    "538976800",  # Online Status
    
    # Reserved/Extended registers
    "10035",      # Reserved 1
    "10034",      # Reserved 2
    "10100",      # Reserved 3
    "538976523",  # Reserved IP
    "538976564",  # Reserved Config 1
    "538976568",  # Reserved Config 2
    "539006279",  # Remote IP
    "539006281",  # Session ID
    "539006282",  # Connection Status
    "539006283",  # Auth Status
    "539006284",  # Protocol Status
    "539006285",  # Data Status
    "539006286",  # Error Status
    "539006287",  # Warning Status
    "539006288",  # Info Status
    "539006290",  # System Mode
    "539006291",  # Control Mode
    "539006292",  # Reserved Status
    "539006293",  # Reserved Info
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
        base_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
        self._attr_name = f"Huawei Charger {base_name}"
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
