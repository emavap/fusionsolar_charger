import json
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SENSITIVE_REGISTERS

_LOGGER = logging.getLogger(__name__)

SERVICE_DUMP_CONFIG_SIGNALS = "dump_config_signals"
SERVICE_SET_CONFIG_SIGNAL = "set_config_signal"
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"

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

_SET_CONFIG_SIGNAL_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("param_id"): cv.string,
        vol.Required("value"): vol.Any(str, int, float, bool),
    }
)

_START_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("gun_number", default=1): vol.Coerce(int),
        vol.Optional("account_id"): vol.Any(str, int),
        vol.Optional("refresh", default=True): cv.boolean,
    }
)

_STOP_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("gun_number", default=1): vol.Coerce(int),
        vol.Optional("order_number"): vol.Any(str, int),
        vol.Optional("serial_number"): cv.string,
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

    async def async_set_config_signal(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        param_id = str(call.data["param_id"]).strip()
        value = _coerce_service_value(call.data["value"])
        coordinators = _get_coordinators(hass, entry_id=entry_id)
        if not coordinators:
            detail = f" entry_id={entry_id}" if entry_id else ""
            _LOGGER.warning(
                "Huawei charger set_config_signal requested but no matching coordinators were found%s",
                detail,
            )
            return

        if len(coordinators) > 1 and not entry_id:
            _LOGGER.warning(
                "Huawei charger set_config_signal requires entry_id when multiple charger entries exist"
            )
            return

        coordinator = coordinators[0]
        success = await hass.async_add_executor_job(
            coordinator.set_config_value,
            param_id,
            value,
        )
        if success:
            _LOGGER.warning(
                "Huawei charger set_config_signal succeeded entry_id=%s param_id=%s value=%s",
                coordinator.entry.entry_id,
                param_id,
                value,
            )
        else:
            _LOGGER.warning(
                "Huawei charger set_config_signal failed entry_id=%s param_id=%s value=%s",
                coordinator.entry.entry_id,
                param_id,
                value,
            )

    async def async_start_charge(call: ServiceCall) -> None:
        coordinator = _resolve_single_coordinator(hass, call, SERVICE_START_CHARGE)
        if coordinator is None:
            return

        gun_number = call.data.get("gun_number", 1)
        account_id = call.data.get("account_id")
        refresh = call.data.get("refresh", True)
        success = await hass.async_add_executor_job(
            lambda: coordinator.start_charge(
                gun_number=gun_number,
                account_id=account_id,
            )
        )
        await _log_charge_action_result(
            coordinator=coordinator,
            action=SERVICE_START_CHARGE,
            success=success,
            extra={
                "gun_number": gun_number,
                "account_id": account_id,
            },
            refresh=refresh,
        )

    async def async_stop_charge(call: ServiceCall) -> None:
        coordinator = _resolve_single_coordinator(hass, call, SERVICE_STOP_CHARGE)
        if coordinator is None:
            return

        gun_number = call.data.get("gun_number", 1)
        order_number = call.data.get("order_number")
        serial_number = call.data.get("serial_number")
        refresh = call.data.get("refresh", True)
        success = await hass.async_add_executor_job(
            lambda: coordinator.stop_charge(
                gun_number=gun_number,
                order_number=order_number,
                serial_number=serial_number,
            )
        )
        await _log_charge_action_result(
            coordinator=coordinator,
            action=SERVICE_STOP_CHARGE,
            success=success,
            extra={
                "gun_number": gun_number,
                "order_number": order_number,
                "serial_number": serial_number,
            },
            refresh=refresh,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_CONFIG_SIGNALS,
        async_dump_config_signals,
        schema=_DUMP_CONFIG_SIGNALS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONFIG_SIGNAL,
        async_set_config_signal,
        schema=_SET_CONFIG_SIGNAL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGE,
        async_start_charge,
        schema=_START_CHARGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGE,
        async_stop_charge,
        schema=_STOP_CHARGE_SCHEMA,
    )
    domain_data["_services_registered"] = True


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister component services when no charger entries remain."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get("_services_registered"):
        return

    if hass.services.has_service(DOMAIN, SERVICE_DUMP_CONFIG_SIGNALS):
        hass.services.async_remove(DOMAIN, SERVICE_DUMP_CONFIG_SIGNALS)
    if hass.services.has_service(DOMAIN, SERVICE_SET_CONFIG_SIGNAL):
        hass.services.async_remove(DOMAIN, SERVICE_SET_CONFIG_SIGNAL)
    if hass.services.has_service(DOMAIN, SERVICE_START_CHARGE):
        hass.services.async_remove(DOMAIN, SERVICE_START_CHARGE)
    if hass.services.has_service(DOMAIN, SERVICE_STOP_CHARGE):
        hass.services.async_remove(DOMAIN, SERVICE_STOP_CHARGE)
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


def _resolve_single_coordinator(hass: HomeAssistant, call: ServiceCall, service_name: str):
    entry_id = call.data.get("entry_id")
    coordinators = _get_coordinators(hass, entry_id=entry_id)
    if not coordinators:
        detail = f" entry_id={entry_id}" if entry_id else ""
        _LOGGER.warning(
            "Huawei charger %s requested but no matching coordinators were found%s",
            service_name,
            detail,
        )
        return None

    if len(coordinators) > 1 and not entry_id:
        _LOGGER.warning(
            "Huawei charger %s requires entry_id when multiple charger entries exist",
            service_name,
        )
        return None

    return coordinators[0]


async def _log_charge_action_result(
    *,
    coordinator,
    action: str,
    success: bool,
    extra: dict,
    refresh: bool,
) -> None:
    if success and refresh:
        await coordinator.async_request_refresh()

    formatted_extra = " ".join(
        f"{key}={value}"
        for key, value in extra.items()
        if value not in (None, "")
    )
    if success:
        _LOGGER.warning(
            "Huawei charger %s succeeded entry_id=%s%s%s",
            action,
            coordinator.entry.entry_id,
            " " if formatted_extra else "",
            formatted_extra,
        )
    else:
        _LOGGER.warning(
            "Huawei charger %s failed entry_id=%s%s%s",
            action,
            coordinator.entry.entry_id,
            " " if formatted_extra else "",
            formatted_extra,
        )


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


def _coerce_service_value(value):
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return stripped

    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    try:
        if "." in stripped:
            number = float(stripped)
            return int(number) if number.is_integer() else number
        return int(stripped)
    except ValueError:
        return stripped
