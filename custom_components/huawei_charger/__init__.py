from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.frontend import add_extra_js_url
import os
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number"]

# Custom cards to register
CUSTOM_CARDS = [
    "huawei-charger-status-card.js",
    "huawei-charger-control-card.js", 
    "huawei-charger-energy-card.js",
    "huawei-charger-info-card.js"
]

async def register_custom_cards(hass: HomeAssistant) -> None:
    """Register custom Lovelace cards by copying to www directory."""
    import shutil

    component_dir = os.path.dirname(__file__)
    source_www_dir = os.path.join(component_dir, "www")
    ha_www_dir = hass.config.path("www")
    target_dir = os.path.join(ha_www_dir, "community", "huawei_charger")

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_cards_registered"):
        return

    def _copy_cards():
        """Copy card files on a worker thread to avoid blocking the event loop."""
        os.makedirs(target_dir, exist_ok=True)
        copied = []
        missing = []

        for card_file in CUSTOM_CARDS:
            source_path = os.path.join(source_www_dir, card_file)
            target_path = os.path.join(target_dir, card_file)
            if os.path.exists(source_path):
                shutil.copy2(source_path, target_path)
                copied.append(card_file)
            else:
                missing.append(card_file)

        return copied, missing

    try:
        copied_cards, missing_cards = await hass.async_add_executor_job(_copy_cards)

        for card_file in copied_cards:
            card_url = f"/local/community/huawei_charger/{card_file}"
            add_extra_js_url(hass, card_url)
            _LOGGER.info("Registered custom card: %s", card_file)

        for missing in missing_cards:
            _LOGGER.warning("Custom card file not found: %s", os.path.join(source_www_dir, missing))

        domain_data["_cards_registered"] = True
        _LOGGER.info("Huawei Charger custom card registration completed")

    except Exception as err:
        _LOGGER.error("Failed to register custom cards: %s", err)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei Charger from a config entry."""
    from .coordinator import HuaweiChargerCoordinator

    # Register custom cards automatically
    await register_custom_cards(hass)

    coordinator = HuaweiChargerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
