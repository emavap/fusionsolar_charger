import json
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SENSITIVE_REGISTERS

_LOGGER = logging.getLogger(__name__)

SERVICE_DUMP_CONFIG_SIGNALS = "dump_config_signals"

_SESSION_CONTROL_KEYWORDS = (
    "auth",
    "authorization",
    "charge now",
    "disable",
    "enable",
    "lock",
    "manual",
    "mode",
    "plug",
    "prefer",
    "remote",
    "rfid",
    "schedule",
    "scheduled",
    "start",
    "stop",
    "trip",
    "unlock",
    "work",
)

_DUMP_CONFIG_SIGNALS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("refresh", default=True): cv.boolean,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register component services once per Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_services_registered"):
        return

    async def async_dump_config_signals(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        refresh = call.data.get("refresh", True)
        coordinators = _get_coordinators(hass, entry_id=entry_id)
        if not coordinators:
            detail = f" entry_id={entry_id}" if entry_id else ""
            _LOGGER.warning(
                "Huawei charger dump_config_signals requested but no matching coordinators were found%s",
                detail,
            )
            return

        for coordinator in coordinators:
            if refresh:
                try:
                    await hass.async_add_executor_job(_refresh_config_signals, coordinator)
                except Exception as err:
                    _LOGGER.warning(
                        "Huawei charger config signal refresh failed for entry_id=%s: %s",
                        coordinator.entry.entry_id,
                        err,
                    )
                    continue

            dump = build_config_signal_dump(coordinator)
            _LOGGER.warning(
                "Huawei charger config signal dump entry_id=%s\n%s",
                coordinator.entry.entry_id,
                dump,
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_CONFIG_SIGNALS,
        async_dump_config_signals,
        schema=_DUMP_CONFIG_SIGNALS_SCHEMA,
    )
    domain_data["_services_registered"] = True


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister component services when no charger entries remain."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get("_services_registered"):
        return

    if hass.services.has_service(DOMAIN, SERVICE_DUMP_CONFIG_SIGNALS):
        hass.services.async_remove(DOMAIN, SERVICE_DUMP_CONFIG_SIGNALS)
    domain_data["_services_registered"] = False


def _get_coordinators(hass: HomeAssistant, *, entry_id: Optional[str] = None) -> list:
    coordinators = []
    for key, value in hass.data.get(DOMAIN, {}).items():
        if str(key).startswith("_"):
            continue
        if entry_id and key != entry_id:
            continue
        if hasattr(value, "fetch_wallbox_config_probe"):
            coordinators.append(value)
    return coordinators


def _refresh_config_signals(coordinator) -> None:
    coordinator._ensure_device_context()
    if not coordinator.wallbox_dn or not coordinator.wallbox_dn_id:
        coordinator.fetch_wallbox_info()
    else:
        coordinator.fetch_wallbox_config_probe()
        coordinator._update_register_debug_state()


def build_config_signal_dump(coordinator) -> str:
    """Return a human-readable dump of charger config signals."""
    details = getattr(coordinator, "config_signal_details", {}) or {}
    visible_items = [
        dict(item)
        for signal_id, item in details.items()
        if str(signal_id) not in SENSITIVE_REGISTERS
    ]
    visible_items.sort(key=_signal_sort_key)

    if not visible_items:
        return "No config signals discovered. Enable detailed Huawei logging and rerun the service after a successful refresh."

    candidate_items = []
    for item in visible_items:
        keywords = _matching_keywords(item)
        if not keywords:
            continue
        candidate = dict(item)
        candidate["_keywords"] = keywords
        candidate_items.append(candidate)

    lines = [
        (
            "summary: "
            f"signal_count={len(visible_items)} "
            f"candidate_count={len(candidate_items)} "
            f"entry_host={getattr(coordinator, 'auth_host', 'unknown')}"
        )
    ]

    if candidate_items:
        lines.append("session_control_candidates:")
        for item in candidate_items:
            lines.append(f"  - {_format_signal_item(item, include_keywords=True)}")
    else:
        lines.append("session_control_candidates: none")

    lines.append("full_catalog:")
    for item in visible_items:
        lines.append(f"  - {_format_signal_item(item)}")

    return "\n".join(lines)


def _signal_sort_key(item: dict) -> tuple:
    signal_id = str(item.get("id", ""))
    return (0, int(signal_id)) if signal_id.isdigit() else (1, signal_id)


def _matching_keywords(item: dict) -> list[str]:
    haystacks = [
        str(item.get("name", "")).lower(),
        _compact_value(item.get("options", "")).lower(),
        _compact_value(item.get("range", "")).lower(),
    ]
    matches = []
    for keyword in _SESSION_CONTROL_KEYWORDS:
        if any(keyword in haystack for haystack in haystacks):
            matches.append(keyword)
    return matches


def _format_signal_item(item: dict, *, include_keywords: bool = False) -> str:
    parts = [f"id={item.get('id')}"]

    for key in (
        "name",
        "value",
        "default",
        "writable",
        "read_only",
        "rw_flag",
        "min",
        "max",
        "step",
    ):
        value = item.get(key)
        if value is not None:
            parts.append(f"{key}={_compact_value(value)}")

    if item.get("options") not in (None, "", [], {}):
        parts.append(f"options={_compact_value(item.get('options'))}")
    if item.get("range") not in (None, "", [], {}):
        parts.append(f"range={_compact_value(item.get('range'))}")
    if include_keywords and item.get("_keywords"):
        parts.append(f"keywords={','.join(item['_keywords'])}")

    return " ".join(parts)


def _compact_value(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    else:
        text = str(value)

    if len(text) > 180:
        return f"{text[:177]}..."
    return text
