
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfPower

from .const import DOMAIN, REGISTER_NAME_MAP

INTERESTING_SENSOR_REGISTERS = [
    "538976516",  # Device IP
    # REMOVED,    # Session Energy
    "2101259",    # Phase A Voltage
    # REMOVED,    # Total Energy
    # REMOVED,      # Charging State
    "20016",      # Charging Enabled
    "20011",      # Device Name
    "20010",      # Charging Mode
    # REMOVED,      # A Output Current
    "10008",      # Total Energy Charged
    "10001",      # Software Version
    "20013",      # Lock Status
    "20017",      # Plugged In
    "20029"       # Device Serial Number
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for reg_id in INTERESTING_SENSOR_REGISTERS:
        entities.append(HuaweiChargerSensor(coordinator, reg_id))
    async_add_entities(entities)

class HuaweiChargerSensor(SensorEntity):
    def __init__(self, coordinator, reg_id):
        self.coordinator = coordinator
        self._reg_id = reg_id
        self._attr_name = REGISTER_NAME_MAP.get(reg_id, f"Register {reg_id}")
        self._attr_unique_id = f"{coordinator.entry.entry_id}_sensor_{reg_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self._reg_id)

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self):
        return {
            "register_id": self._reg_id
        }
