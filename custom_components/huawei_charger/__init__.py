from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    DOMAIN as LOVELACE_DOMAIN,
)
from homeassistant.const import CONF_URL
import os
import logging
from collections.abc import Mapping

from .const import DOMAIN
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number", "binary_sensor", "button"]

# Custom cards to register
CUSTOM_CARDS = [
    "huawei-charger-status-card.js",
    "huawei-charger-control-card.js", 
    "huawei-charger-energy-card.js",
    "huawei-charger-info-card.js"
]


def _get_lovelace_resources(hass: HomeAssistant):
    """Return the Lovelace resources collection across HA API variants."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if lovelace_data is None:
        return None
    if isinstance(lovelace_data, Mapping):
        return lovelace_data.get("resources")
    return getattr(lovelace_data, "resources", None)


def _get_resource_url(item) -> str | None:
    """Read a Lovelace resource URL from dict-like or object-like items."""
    if isinstance(item, Mapping):
        return item.get(CONF_URL)
    return getattr(item, CONF_URL, None)


async def _register_lovelace_resources(hass: HomeAssistant, card_urls: list[str]) -> None:
    """Register custom cards as Lovelace module resources when available."""
    lovelace_resources = _get_lovelace_resources(hass)
    if lovelace_resources is None or not hasattr(lovelace_resources, "async_create_item"):
        return

    await lovelace_resources.async_get_info()
    existing_urls = {
        _get_resource_url(item)
        for item in (lovelace_resources.async_items() or [])
        if _get_resource_url(item)
    }
    for card_url in card_urls:
        if card_url in existing_urls:
            continue
        await lovelace_resources.async_create_item(
            {
                CONF_URL: card_url,
                CONF_RESOURCE_TYPE_WS: "module",
            }
        )
        _LOGGER.info("Registered Lovelace resource: %s", card_url)

async def register_custom_cards(hass: HomeAssistant) -> None:
    """Register custom Lovelace cards by copying to www directory."""
    import shutil

    component_dir = os.path.dirname(__file__)
    source_www_dir = os.path.join(component_dir, "www")
    ha_www_dir = hass.config.path("www")
    target_dirs = [
        os.path.join(ha_www_dir, "community", "huawei_charger"),
        os.path.join(ha_www_dir, "community", "huawei-charger"),
    ]

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_cards_registered"):
        return

    def _copy_cards():
        """Copy card files on a worker thread to avoid blocking the event loop."""
        copied = []
        missing = []

        for target_dir in target_dirs:
            os.makedirs(target_dir, exist_ok=True)

        for card_file in CUSTOM_CARDS:
            source_path = os.path.join(source_www_dir, card_file)
            if os.path.exists(source_path):
                for target_dir in target_dirs:
                    shutil.copy2(source_path, os.path.join(target_dir, card_file))
                copied.append(card_file)
            else:
                missing.append(card_file)

        return copied, missing

    try:
        copied_cards, missing_cards = await hass.async_add_executor_job(_copy_cards)
        card_urls = [
            f"/local/community/huawei_charger/{card_file}"
            for card_file in copied_cards
        ]

        for card_file in copied_cards:
            card_url = f"/local/community/huawei_charger/{card_file}"
            add_extra_js_url(hass, card_url)
            _LOGGER.info("Registered custom card: %s", card_file)

        await _register_lovelace_resources(hass, card_urls)

        for missing in missing_cards:
            _LOGGER.info("Custom card file not found: %s", os.path.join(source_www_dir, missing))

        domain_data["_cards_registered"] = True
        _LOGGER.info("Huawei Charger custom card registration completed")

    except Exception as err:
        _LOGGER.error("Failed to register custom cards: %s", err)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei Charger from a config entry."""
    from .coordinator import HuaweiChargerCoordinator

    # Register custom cards automatically
    await register_custom_cards(hass)
    async_register_services(hass)

    coordinator = HuaweiChargerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not any(not str(key).startswith("_") for key in hass.data[DOMAIN]):
            async_unregister_services(hass)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
