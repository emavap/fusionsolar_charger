from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .session_state import charging_state


SESSION_CONTROL_PATH = "FusionSolar cloud session endpoints from the APK (start-charge/stop-charge)"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [HuaweiChargerChargingSwitch(coordinator)]

    registry = er.async_get(hass)
    active_unique_ids = {entity.unique_id for entity in entities}
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain == "switch"
            and registry_entry.unique_id
            and registry_entry.unique_id.startswith(f"{entry.entry_id}_")
            and registry_entry.unique_id not in active_unique_ids
        ):
            registry.async_remove(registry_entry.entity_id)

    async_add_entities(entities)


class HuaweiChargerChargingSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = "Charging"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_charging_switch"
        self._attr_icon = "mdi:ev-station"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def available(self):
        state, _ = charging_state(self.coordinator)
        if state is not None:
            return True
        return bool(
            self.coordinator.wallbox_dn_id
            or self.coordinator.wallbox_dn
            or getattr(self.coordinator, "data", None)
            or getattr(self.coordinator, "param_values", None)
        )

    @property
    def is_on(self):
        state, _ = charging_state(self.coordinator)
        return bool(state)

    @property
    def extra_state_attributes(self):
        state, source = charging_state(self.coordinator)
        return {
            "source_register": source,
            "device_status_raw": self.coordinator.get_register_value("device_status"),
            "charge_store_raw": self.coordinator.get_register_value("charge_store"),
            "derived_state": state,
            "control_path": SESSION_CONTROL_PATH,
        }

    async def async_turn_on(self, **kwargs):
        success = await self.hass.async_add_executor_job(self.coordinator.start_charge)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        success = await self.hass.async_add_executor_job(self.coordinator.stop_charge)
        if success:
            await self.coordinator.async_request_refresh()
