from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HuaweiChargerActionButton(
                coordinator,
                key="start_charge",
                name="Start Charging",
                icon="mdi:play-circle",
            ),
            HuaweiChargerActionButton(
                coordinator,
                key="stop_charge",
                name="Stop Charging",
                icon="mdi:stop-circle",
            ),
        ]
    )


class HuaweiChargerActionButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, *, key, name, icon):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._action_key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}_button"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Huawei Charger",
            "manufacturer": "Huawei",
        }

    @property
    def available(self):
        return bool(self.coordinator.wallbox_dn_id or self.coordinator.wallbox_dn or self.coordinator.data)

    async def async_press(self):
        if self._action_key == "start_charge":
            success = await self.hass.async_add_executor_job(self.coordinator.start_charge)
        else:
            success = await self.hass.async_add_executor_job(self.coordinator.stop_charge)

        if success:
            await self.coordinator.async_request_refresh()
