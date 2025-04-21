from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower

from .const import DOMAIN, REGISTER_NAME_MAP

INTERESTING_SENSOR_REGISTERS = [
    "538976516", "2101259",
    "20011", "10008", "10001", "20013", "20017", "20029"
]

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

    @property
    def extra_state_attributes(self):
        return {
            "register_id": self._reg_id
        }
