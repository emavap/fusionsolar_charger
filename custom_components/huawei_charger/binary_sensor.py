from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .session_state import vehicle_connected_state


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        HuaweiChargerCredentialsRejectedBinarySensor(coordinator),
        HuaweiChargerVehicleConnectedBinarySensor(coordinator),
    ]

    registry = er.async_get(hass)
    active_unique_ids = {entity.unique_id for entity in entities}
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain == "binary_sensor"
            and registry_entry.unique_id
            and registry_entry.unique_id.startswith(f"{entry.entry_id}_")
            and registry_entry.unique_id not in active_unique_ids
        ):
            registry.async_remove(registry_entry.entity_id)

    async_add_entities(entities)


class HuaweiChargerCredentialsRejectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = "Reauthentication Required"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_reauthentication_required"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def is_on(self):
        return self.coordinator.is_reauth_required()

    @property
    def available(self):
        return True

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        debug_data = self.coordinator.debug_data
        return {
            "suggested_action": "Reconfigure the integration credentials in Home Assistant.",
            "last_update_error": debug_data.get("last_update_error"),
            "last_update_at": debug_data.get("last_update_at"),
            "last_write_error": debug_data.get("last_write_error"),
            "last_write_at": debug_data.get("last_write_at"),
        }


class HuaweiChargerVehicleConnectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = "Vehicle Connected"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_vehicle_connected"
        self._attr_device_class = BinarySensorDeviceClass.PLUG
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def is_on(self):
        state, _ = vehicle_connected_state(self.coordinator)
        return bool(state)

    @property
    def available(self):
        state, _ = vehicle_connected_state(self.coordinator)
        return state is not None

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        state, source = vehicle_connected_state(self.coordinator)
        return {
            "source_register": source,
            "plugged_in_raw": self.coordinator.get_register_value("20017"),
            "device_status_raw": self.coordinator.get_register_value("device_status"),
            "charge_store_raw": self.coordinator.get_register_value("charge_store"),
            "derived_state": state,
        }
