import logging
import re
from datetime import timedelta, datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import asyncio
import json
import time

import requests

from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    CONF_ENABLE_LOGGING,
    DOMAIN,
    CONF_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_ENABLE_LOGGING,
    DEFAULT_FUSIONSOLAR_HOST,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE_OFFSET,
    WRITABLE_REGISTERS,
)

_LOGGER = logging.getLogger(__name__)

_NUMERIC_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")
APP_TOKEN_PATH = "/rest/neteco/appauthen/v1/smapp/app/token"


class FusionSolarRequestError(UpdateFailed):
    """Raised when FusionSolar returns an error payload."""

    def __init__(self, message: str, response_excerpt=None):
        super().__init__(message)
        self.response_excerpt = response_excerpt


class AuthenticationFailed(FusionSolarRequestError):
    """Raised when FusionSolar signals an authentication failure."""


class HuaweiChargerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        update_seconds = entry.options.get(CONF_INTERVAL, entry.data.get(CONF_INTERVAL, 30))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_seconds),
        )
        self.hass = hass
        self.entry = entry
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.auth_host = entry.data.get(CONF_HOST, DEFAULT_FUSIONSOLAR_HOST)
        self.verify_ssl = entry.options.get(CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, False))
        self.enable_logging = entry.options.get(
            CONF_ENABLE_LOGGING,
            entry.data.get(CONF_ENABLE_LOGGING, DEFAULT_ENABLE_LOGGING),
        )
        self.request_timeout = DEFAULT_REQUEST_TIMEOUT

        self.token = None
        self.headers = {}
        self.region_ip = None
        self.dn_id = None
        self.wallbox_dn = None
        self.wallbox_dn_id = None
        self.station_values = {}
        self.param_values = {}
        self.config_signal_details = {}
        self.config_signal_values = {}
        self.locale = self._derive_locale()
        self.timezone_offset = self._derive_timezone_offset()
        self.debug_data = self._build_debug_data()
        self._request_counter = 0
        self._last_realtime_signal_catalog = None
        self._last_config_signal_catalog = None
        self._history_probe_completed = False
        self._debug_log(
            "Huawei coordinator initialized host=%s verify_ssl=%s update_interval=%ss",
            self.auth_host,
            self.verify_ssl,
            update_seconds,
        )

    async def _async_update_data(self):
        cycle_started = time.monotonic()
        self._debug_log(
            "Huawei update cycle started host=%s token_present=%s region_ip=%s",
            self.auth_host,
            bool(self.token),
            self.region_ip,
        )
        for attempt in range(3):
            try:
                await self.hass.async_add_executor_job(self._ensure_device_context)
                await self.hass.async_add_executor_job(self.fetch_wallbox_info)
                self._record_update_debug(
                    status="success",
                    duration_ms=self._elapsed_ms(cycle_started),
                )
                return self.param_values

            except AuthenticationFailed as err:
                _LOGGER.warning("Authentication failure on update attempt %s: %s", attempt + 1, err)
                self._reset_auth_state()
                self._clear_register_debug_state()
                self._record_update_debug(
                    status="error",
                    error=str(err),
                    duration_ms=self._elapsed_ms(cycle_started),
                    response_excerpt=getattr(err, "response_excerpt", None),
                )
                if attempt == 2:
                    raise ConfigEntryAuthFailed("Authentication failed after retries") from err
                await asyncio.sleep(2 ** attempt)
            except Exception as err:
                _LOGGER.warning("Update attempt %s/3 failed: %s", attempt + 1, err)
                self._reset_auth_state()
                self._clear_register_debug_state()
                self._record_update_debug(
                    status="error",
                    error=str(err),
                    duration_ms=self._elapsed_ms(cycle_started),
                    response_excerpt=getattr(err, "response_excerpt", None),
                )
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise UpdateFailed(f"Update failed after retries: {err}") from err

    def authenticate(self):
        payload = {
            "userName": self.username,
            "value": self.password,
            "grantType": "password",
            "verifyCode": "",
            "appClientId": "86366133-B8B5-41FA-8EB9-E5A64229E3E1",
        }
        last_response_excerpt = None

        for candidate_host in self._authentication_hosts():
            response = self._request_post(
                self._app_token_url(candidate_host),
                json=payload,
                headers={"Content-Type": "application/json"},
                operation=f"authenticate:{candidate_host}",
            )
            data = self._json_or_error(response, f"authenticate:{candidate_host}")
            token_data = data.get("data") or {}
            last_response_excerpt = self._json_dump(data)

            token = self._extract_token(token_data)
            self._debug_log(
                "Auth candidate=%s token_present=%s region_host=%s data_keys=%s",
                candidate_host,
                bool(token),
                self._extract_region_host(token_data),
                sorted(token_data.keys()) if isinstance(token_data, dict) else None,
            )
            if not token:
                continue

            self.token = token
            self.region_ip = self._extract_region_host(token_data) or candidate_host

            cookie_locale = self.locale.replace("_", "-").lower()
            self.headers = {
                "Cookie": (
                    f"locale={cookie_locale};bspsession={self.token};"
                    f"dp-session={self.token}; Secure; HttpOnly"
                ),
                "Content-Type": "application/json",
                "x-timezone-offset": str(self.timezone_offset),
                "User-Agent": "iCleanPower/24.6.102006",
            }

            roa_rand = token_data.get("roaRand") or token_data.get("csrfToken")
            if roa_rand:
                self.headers["roaRand"] = str(roa_rand)

            self.fetch_station_dn()
            return

        raise UpdateFailed(
            f"Authentication response missing access token"
            f"{f': {last_response_excerpt}' if last_response_excerpt else ''}"
        )

    def fetch_station_dn(self):
        url = f"https://{self.region_ip}:32800/rest/pvms/web/station/v1/station/station-list"
        payload = {
            "locale": self.locale,
            "sortId": "createTime",
            "timeZone": f"{self.timezone_offset / 60:.2f}",
            "pageSize": "11",
            "supportMDevice": "1",
            "sortDir": "DESC",
            "curPage": 1
        }
        response = self._request_post(
            url,
            json=payload,
            headers=self.headers,
            operation="station-list",
        )
        data = self._json_or_error(response, "station-list")
        
        if not data.get("data", {}).get("list"):
            raise ValueError("No stations found in account")
        
        station = data["data"]["list"][0]
        self.dn_id = station["dn"]
        self.station_values = {}
        charge_store = station.get("chargeStore")
        if charge_store is not None:
            self.station_values["charge_store"] = str(charge_store)

    def fetch_wallbox_info(self):
        url = f"https://{self.region_ip}:32800/rest/neteco/web/config/device/v1/device-list"
        payload = (
            f"conditionParams.curPage=0&"
            f"conditionParams.mocTypes=60080&"
            f"conditionParams.parentDn={self.dn_id}&"
            f"conditionParams.recordperpage=500"
        )
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        response = self._request_post(
            url,
            data=payload,
            headers=headers,
            operation="wallbox-info",
        )

        data = self._json_or_error(response, "wallbox-info", default={})
        self._debug_log("Full wallbox fetch response: %s", self._json_dump(data))

        if not data.get("data") or not isinstance(data["data"], list) or len(data["data"]) == 0:
            raise ValueError("No wallbox devices found in station")

        wallbox = data["data"][0]
        self.wallbox_dn = wallbox.get("dn")
        self.wallbox_dn_id = wallbox["dnId"]
        self.fetch_wallbox_config_probe()
        self.param_values = self._normalize_param_values(wallbox.get("paramValues", {}))
        device_status = wallbox.get("deviceStatus")
        if device_status is not None:
            self.param_values["device_status"] = str(device_status)
        if self._should_fetch_realtime_data(self.param_values):
            realtime_values = self.fetch_wallbox_realtime_data()
            if realtime_values:
                self._debug_log(
                    "Using wallbox realtime-data signals because device-list returned limited paramValues"
                )
                self.param_values.update(realtime_values)
        self.param_values.update(self.station_values)
        self._update_register_debug_state()

        if self.param_values or self.config_signal_values:
            available_registers = sorted(
                {str(reg_id) for reg_id in self.param_values.keys()}.union(self.config_signal_values.keys())
            )
            self._debug_log("Available register IDs from charger: %s", sorted(available_registers))

            for reg_id in WRITABLE_REGISTERS + ["10009", "10010", "20017"]:
                reg_value = self.get_register_value(reg_id)
                if reg_value is not None:
                    self._debug_log("Register %s value: %s", reg_id, reg_value)

        return self.param_values

    def fetch_wallbox_realtime_data(self):
        if not self.wallbox_dn:
            self._debug_log("Skipping wallbox realtime-data request because wallbox dn is missing")
            return {}

        url = f"https://{self.region_ip}:32800/rest/pvms/web/device/v1/device-realtime-data"
        response = self._request_get(
            url,
            params={
                "deviceDn": self.wallbox_dn,
                "_": round(time.time() * 1000),
            },
            headers=self.headers,
            operation="wallbox-realtime",
        )
        data = self._json_or_error(response, "wallbox-realtime", default={})
        self._debug_log("Full wallbox realtime response: %s", self._json_dump(data))

        signal_values = self._extract_signal_values(data)
        signal_catalog = self._extract_signal_catalog(data)
        self._log_realtime_signal_catalog(signal_catalog)
        if signal_values:
            self._debug_log(
                "Available realtime register IDs from charger: %s",
                sorted(signal_values.keys()),
            )
            if not self._history_probe_completed:
                self.fetch_wallbox_history_probe(sorted(signal_values.keys()))
            return self._normalize_param_values(signal_values)

        self._debug_log("Wallbox realtime-data response did not contain usable signals")
        return {}

    def fetch_wallbox_config_probe(self):
        if not self.wallbox_dn and not self.wallbox_dn_id:
            self._debug_log("Skipping wallbox config probes because dn and dnId are missing")
            self.config_signal_values = {}
            return {}

        discovered_values = {}
        for probe in self._config_probe_requests():
            try:
                response = self._request_get(
                    probe["url"],
                    params=probe.get("params"),
                    headers=self.headers,
                    operation=probe["operation"],
                )
                data = self._json_or_error(response, probe["operation"], default={})
                self._debug_log(
                    "Full %s response: %s",
                    probe["operation"],
                    self._json_dump(data),
                )
                signal_catalog = self._extract_config_signal_catalog(data)
                self._store_config_signal_details(signal_catalog)
                discovered_values.update(self._config_signal_values_from_catalog(signal_catalog))
                self._log_config_signal_catalog(probe["operation"], signal_catalog)
                self._debug_log(
                    "Wallbox config probe %s returned signal_ids=%s",
                    probe["operation"],
                    sorted(self._extract_signal_ids(data)),
                )
            except Exception as err:
                self._debug_log(
                    "Wallbox config probe %s failed: %s",
                    probe["operation"],
                    err,
                )
        self.config_signal_values = self._normalize_param_values(discovered_values)
        return self.config_signal_values

    def _config_probe_requests(self):
        timestamp = round(time.time() * 1000)
        if not self.wallbox_dn:
            return []

        return [
            {
                "method": "GET",
                "operation": "wallbox-config-get-dn",
                "url": f"https://{self.region_ip}:32800/rest/pvms/web/device/v1/deviceExt/get-config-signals",
                "params": {"dn": self.wallbox_dn, "_": timestamp},
            }
        ]

    def fetch_wallbox_history_probe(self, realtime_signal_ids):
        if not self.wallbox_dn:
            return

        requested_signal_ids = self._history_probe_signal_ids(realtime_signal_ids)
        url = f"https://{self.region_ip}:32800/rest/pvms/web/device/v1/device-history-data"
        params = [("signalIds", signal_id) for signal_id in requested_signal_ids]
        params.extend(
            [
                ("deviceDn", self.wallbox_dn),
                ("date", int(time.time() * 1000)),
                ("_", round(time.time() * 1000)),
            ]
        )

        try:
            response = self._request_get(
                url,
                params=params,
                headers=self.headers,
                operation="wallbox-history",
            )
            data = self._json_or_error(response, "wallbox-history", default={})
            self._debug_log("Full wallbox history response: %s", self._json_dump(data))
            returned_signal_ids = sorted(self._extract_signal_ids(data))
            self._debug_log(
                "Wallbox history probe requested_ids=%s returned_ids=%s",
                requested_signal_ids,
                returned_signal_ids,
            )
        except Exception as err:
            self._debug_log("Wallbox history probe failed: %s", err)
        finally:
            self._history_probe_completed = True

    def set_config_value(self, param_id: str, value, retries=3):
        write_started = time.monotonic()
        self._record_write_debug(
            status="pending",
            param_id=param_id,
            value=value,
            attempts=0,
        )

        try:
            self._ensure_device_context()
            if not self.wallbox_dn or not self.wallbox_dn_id:
                self.fetch_wallbox_info()
        except Exception as err:
            _LOGGER.error("Unable to prepare charger context before writing %s: %s", param_id, err)
            self._record_write_debug(
                status="error",
                param_id=param_id,
                value=value,
                error=str(err),
                attempts=0,
                duration_ms=self._elapsed_ms(write_started),
            )
            return False

        for attempt in range(retries):
            try:
                last_write_error = None
                response_excerpt = None
                for target in self._set_config_targets(param_id, value):
                    try:
                        headers = self.headers.copy()
                        if target.get("data") is not None:
                            headers["Content-Type"] = "application/x-www-form-urlencoded"
                        response = self._request_post(
                            target["url"],
                            json=target.get("json"),
                            data=target.get("data"),
                            headers=headers,
                            operation=target["operation"],
                        )
                        data = self._json_or_error(
                            response,
                            target["operation"],
                            default={},
                        )
                        response_excerpt = self._json_dump(data)
                        self._debug_log(
                            "Set config response for %s via %s: %s",
                            param_id,
                            target["operation"],
                            response_excerpt,
                        )
                        if response.status_code == 200:
                            normalized_value = self._convert_register_value(value)
                            self.config_signal_values[str(param_id)] = normalized_value
                            if str(param_id) in self.config_signal_details:
                                self.config_signal_details[str(param_id)]["value"] = normalized_value
                            self._update_register_debug_state()
                            _LOGGER.warning(
                                "Successfully set config %s to %s using %s",
                                param_id,
                                value,
                                target["operation"],
                            )
                            self._record_write_debug(
                                status="success",
                                param_id=param_id,
                                value=value,
                                attempts=attempt + 1,
                                duration_ms=self._elapsed_ms(write_started),
                                response_excerpt=response_excerpt,
                            )
                            return True
                    except AuthenticationFailed:
                        raise
                    except (FusionSolarRequestError, UpdateFailed, requests.RequestException) as err:
                        last_write_error = err
                        response_excerpt = getattr(err, "response_excerpt", response_excerpt)
                        self._debug_log(
                            "Set config target %s failed for %s: %s",
                            target["operation"],
                            param_id,
                            err,
                        )
                if last_write_error is not None:
                    raise last_write_error
            except AuthenticationFailed as err:
                _LOGGER.warning("Authentication expired while writing %s; refreshing token", param_id)
                self._reset_auth_state()
                self._record_write_debug(
                    status="retrying" if attempt < retries - 1 else "error",
                    param_id=param_id,
                    value=value,
                    error=str(err),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(write_started),
                    response_excerpt=getattr(err, "response_excerpt", None),
                )
                try:
                    self._ensure_device_context()
                    if not self.wallbox_dn or not self.wallbox_dn_id:
                        self.fetch_wallbox_info()
                except Exception as refresh_err:
                    _LOGGER.warning(
                        "Unable to restore charger context after auth refresh for %s: %s",
                        param_id,
                        refresh_err,
                    )
                    self._record_write_debug(
                        status="error",
                        param_id=param_id,
                        value=value,
                        error=str(refresh_err),
                        attempts=attempt + 1,
                        duration_ms=self._elapsed_ms(write_started),
                        response_excerpt=getattr(refresh_err, "response_excerpt", None),
                    )
                    break
            except UpdateFailed as err:
                _LOGGER.warning("Set config attempt %s/%s failed: %s", attempt + 1, retries, err)
                self._record_write_debug(
                    status="retrying" if attempt < retries - 1 else "error",
                    param_id=param_id,
                    value=value,
                    error=str(err),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(write_started),
                    response_excerpt=getattr(err, "response_excerpt", None),
                )
            except requests.RequestException as err:
                _LOGGER.warning("Set config attempt %s/%s failed: %s", attempt + 1, retries, err)
                self._record_write_debug(
                    status="retrying" if attempt < retries - 1 else "error",
                    param_id=param_id,
                    value=value,
                    error=str(err),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(write_started),
                )

            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                _LOGGER.error("Failed to set config %s after %s attempts", param_id, retries)

        return False

    def query_charge_process_data(self, gun_number: int = 1):
        """Return live charging session metadata for a charger gun."""
        self._ensure_device_context()
        if not self.wallbox_dn_id:
            self.fetch_wallbox_info()

        url = f"https://{self.region_ip}:32800/rest/neteco/web/homemgr/v1/charger/device/query-process-data"
        payload = {
            "dnId": self.wallbox_dn_id,
            "gunNumber": int(gun_number),
        }
        response = self._request_post(
            url,
            json=payload,
            headers=self.headers,
            operation="charger-query-process-data",
        )
        data = self._json_or_error(response, "charger-query-process-data", default={})
        self._debug_log(
            "Charge process data response gun=%s payload=%s",
            gun_number,
            self._json_dump(data),
        )

        records = data.get("data")
        if isinstance(records, list):
            return records[0] if records else {}
        if isinstance(records, dict):
            return records
        return data if isinstance(data, dict) else {}

    def start_charge(self, *, gun_number: int = 1, account_id=None, retries: int = 3) -> bool:
        """Start a charging session through the FusionSolar cloud API."""
        return self._run_charge_action(
            action_name="start_charge",
            payload_factory=lambda: self._build_start_charge_payload(
                gun_number=gun_number,
                account_id=account_id,
            ),
            retries=retries,
        )

    def stop_charge(
        self,
        *,
        gun_number: int = 1,
        order_number=None,
        serial_number=None,
        retries: int = 3,
    ) -> bool:
        """Stop a charging session through the FusionSolar cloud API."""
        return self._run_charge_action(
            action_name="stop_charge",
            payload_factory=lambda: self._build_stop_charge_payload(
                gun_number=gun_number,
                order_number=order_number,
                serial_number=serial_number,
            ),
            retries=retries,
        )

    def _run_charge_action(self, *, action_name: str, payload_factory, retries: int) -> bool:
        action_started = time.monotonic()
        self._record_write_debug(
            status="pending",
            param_id=action_name,
            value=None,
            attempts=0,
        )

        for attempt in range(retries):
            try:
                payload = payload_factory()
                response = self._request_post(
                    self._charger_action_url(action_name),
                    json=payload,
                    headers=self.headers,
                    operation=f"charger-{action_name}",
                )
                data = self._json_or_error(
                    response,
                    f"charger-{action_name}",
                    default={},
                )
                response_excerpt = self._json_dump(data)
                self._debug_log(
                    "Charge action %s payload=%s response=%s",
                    action_name,
                    self._json_dump(payload),
                    response_excerpt,
                )
                if not self._charge_action_succeeded(data):
                    raise FusionSolarRequestError(
                        f"Huawei charger {action_name} returned an unsuccessful payload",
                        response_excerpt=response_excerpt,
                    )
                self._record_write_debug(
                    status="success",
                    param_id=action_name,
                    value=self._debug_repr(payload),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(action_started),
                    response_excerpt=response_excerpt,
                )
                return True
            except AuthenticationFailed as err:
                self._reset_auth_state()
                self._record_write_debug(
                    status="retrying" if attempt < retries - 1 else "error",
                    param_id=action_name,
                    value=None,
                    error=str(err),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(action_started),
                    response_excerpt=getattr(err, "response_excerpt", None),
                )
                if attempt < retries - 1:
                    continue
            except Exception as err:
                response_excerpt = getattr(err, "response_excerpt", None)
                self._record_write_debug(
                    status="retrying" if attempt < retries - 1 else "error",
                    param_id=action_name,
                    value=None,
                    error=str(err),
                    attempts=attempt + 1,
                    duration_ms=self._elapsed_ms(action_started),
                    response_excerpt=response_excerpt,
                )
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                _LOGGER.error("Huawei charger %s failed after %s attempts: %s", action_name, retries, err)
                return False

        return False

    def _charger_action_url(self, action_name: str) -> str:
        routes = {
            "start_charge": "/rest/neteco/web/homemgr/v1/charger/charge/start-charge",
            "stop_charge": "/rest/neteco/web/homemgr/v1/charger/charge/stop-charge",
        }
        return f"https://{self.region_ip}:32800{routes[action_name]}"

    def _charge_action_succeeded(self, payload) -> bool:
        if not isinstance(payload, dict):
            return True

        success = payload.get("success")
        if isinstance(success, bool):
            return success
        if isinstance(success, str):
            lowered = success.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true"

        for key in ("failCode", "errorCode"):
            value = payload.get(key)
            if value not in (None, "", 0, "0", "0000"):
                return False

        return True

    def _build_start_charge_payload(self, *, gun_number: int, account_id):
        self._ensure_device_context()
        if not self.wallbox_dn_id:
            self.fetch_wallbox_info()

        payload = {
            "dnId": self.wallbox_dn_id,
            "gunNumber": int(gun_number),
        }
        if account_id not in (None, ""):
            payload["accountId"] = account_id
        return payload

    def _build_stop_charge_payload(self, *, gun_number: int, order_number, serial_number):
        self._ensure_device_context()
        if not self.wallbox_dn_id:
            self.fetch_wallbox_info()

        payload = {
            "dnId": self.wallbox_dn_id,
            "gunNumber": int(gun_number),
        }
        if order_number not in (None, ""):
            payload["orderNumber"] = str(order_number)
        if serial_number not in (None, ""):
            payload["serialNumber"] = str(serial_number)

        if "orderNumber" not in payload or "serialNumber" not in payload:
            process_data = self.query_charge_process_data(gun_number=gun_number)
            discovered_order = process_data.get("orderNumber")
            discovered_serial = process_data.get("serialNumber")
            if "orderNumber" not in payload and discovered_order not in (None, ""):
                payload["orderNumber"] = str(discovered_order)
            if "serialNumber" not in payload and discovered_serial not in (None, ""):
                payload["serialNumber"] = str(discovered_serial)

        missing = [field for field in ("orderNumber", "serialNumber") if field not in payload]
        if missing:
            raise ValueError(
                "Unable to stop charging because the active session metadata is incomplete: "
                + ", ".join(missing)
            )
        return payload

    def _set_config_targets(self, param_id, value):
        change_values = [{"id": str(param_id), "value": str(value)}]
        targets = []

        if self.wallbox_dn:
            targets.append(
                {
                    "operation": f"set-config-new:{param_id}",
                    "url": f"https://{self.region_ip}:32800/rest/pvms/web/device/v1/deviceExt/set-config-signals",
                    "json": None,
                    "data": {
                        "dn": self.wallbox_dn,
                        "changeValues": json.dumps(change_values, separators=(",", ":")),
                    },
                }
            )

        return targets

    def _request_post(self, url, *, json=None, data=None, headers=None, operation=None):
        """Wrapper for POST requests with shared settings."""
        self._request_counter += 1
        request_id = self._request_counter
        started = time.monotonic()
        try:
            self._debug_log(
                "Huawei HTTP #%s %s request url=%s json=%s data=%s headers=%s",
                request_id,
                operation or "POST",
                url,
                self._debug_repr(json),
                self._debug_repr(data),
                self._debug_repr(headers),
            )
            response = requests.post(
                url,
                json=json,
                data=data,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.request_timeout,
            )
            self._debug_log(
                "Huawei HTTP #%s %s response status=%s duration_ms=%s headers=%s body=%s",
                request_id,
                operation or "POST",
                response.status_code,
                self._elapsed_ms(started),
                self._response_headers_excerpt(response),
                self._response_excerpt(response),
            )
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as err:
            ssl_hint = " (disable verify_ssl in integration options)" if self.verify_ssl else ""
            raise UpdateFailed(f"SSL error during request{ssl_hint}") from err
        except requests.exceptions.Timeout as err:
            raise UpdateFailed("Request timeout while contacting FusionSolar API") from err
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed("Connection error to FusionSolar API") from err
        except requests.exceptions.HTTPError as err:
            status = err.response.status_code if err.response is not None else "unknown"
            response_excerpt = self._response_excerpt(err.response)
            detail = f": {response_excerpt}" if response_excerpt else ""
            if status in (401, 403):
                raise AuthenticationFailed(
                    f"HTTP {status} authentication error from FusionSolar{detail}",
                    response_excerpt=response_excerpt,
                ) from err
            raise FusionSolarRequestError(
                f"HTTP {status} error while contacting FusionSolar API{detail}",
                response_excerpt=response_excerpt,
            ) from err

    def _request_get(self, url, *, params=None, headers=None, operation=None):
        """Wrapper for GET requests with shared settings."""
        self._request_counter += 1
        request_id = self._request_counter
        started = time.monotonic()
        try:
            self._debug_log(
                "Huawei HTTP #%s %s request url=%s params=%s headers=%s",
                request_id,
                operation or "GET",
                url,
                self._debug_repr(params),
                self._debug_repr(headers),
            )
            response = requests.get(
                url,
                params=params,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.request_timeout,
            )
            self._debug_log(
                "Huawei HTTP #%s %s response status=%s duration_ms=%s headers=%s body=%s",
                request_id,
                operation or "GET",
                response.status_code,
                self._elapsed_ms(started),
                self._response_headers_excerpt(response),
                self._response_excerpt(response),
            )
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as err:
            ssl_hint = " (disable verify_ssl in integration options)" if self.verify_ssl else ""
            raise UpdateFailed(f"SSL error during request{ssl_hint}") from err
        except requests.exceptions.Timeout as err:
            raise UpdateFailed("Request timeout while contacting FusionSolar API") from err
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed("Connection error to FusionSolar API") from err
        except requests.exceptions.HTTPError as err:
            status = err.response.status_code if err.response is not None else "unknown"
            response_excerpt = self._response_excerpt(err.response)
            detail = f": {response_excerpt}" if response_excerpt else ""
            if status in (401, 403):
                raise AuthenticationFailed(
                    f"HTTP {status} authentication error from FusionSolar{detail}",
                    response_excerpt=response_excerpt,
                ) from err
            raise FusionSolarRequestError(
                f"HTTP {status} error while contacting FusionSolar API{detail}",
                response_excerpt=response_excerpt,
            ) from err

    def _authentication_hosts(self):
        hosts = [self.auth_host]
        if self.auth_host != DEFAULT_FUSIONSOLAR_HOST:
            hosts.append(DEFAULT_FUSIONSOLAR_HOST)
        return hosts

    def _app_token_url(self, host):
        return f"https://{host}:32800{APP_TOKEN_PATH}"

    def _extract_token(self, token_data):
        if not isinstance(token_data, dict):
            return None
        return token_data.get("accessToken") or token_data.get("token")

    def _extract_region_host(self, token_data):
        if not isinstance(token_data, dict):
            return None

        for key in ("regionFloatIp", "regionIp", "regionFloatUrl", "service"):
            candidate = self._normalize_host(token_data.get(key))
            if candidate:
                return candidate
        return None

    def _json_or_error(self, response, context, default=None):
        """Parse JSON or raise an UpdateFailed."""
        try:
            return response.json()
        except ValueError as err:
            if default is not None:
                _LOGGER.warning("Response for %s was not JSON: %s", context, err)
                return default
            raise UpdateFailed(f"Invalid JSON response during {context}") from err

    def _normalize_param_values(self, param_values):
        """Convert FusionSolar param values into native Python types."""
        if not isinstance(param_values, dict):
            return {}

        normalized = {}
        for reg_id, value in param_values.items():
            normalized[reg_id] = self._convert_register_value(value)
        return normalized

    def _has_expected_registers(self, param_values):
        expected_registers = set(WRITABLE_REGISTERS).union(
            {"10008", "10009", "10010", "20017", "2101259", "2101260", "2101261"}
        )
        return any(reg_id in param_values for reg_id in expected_registers)

    def _should_fetch_realtime_data(self, param_values):
        realtime_priority_registers = {
            "10003",
            "10008",
            "10009",
            "10010",
            "20017",
        }
        return (not self._has_expected_registers(param_values)) or any(
            reg_id not in param_values for reg_id in realtime_priority_registers
        )

    def _history_probe_signal_ids(self, realtime_signal_ids):
        preferred = [
            "10008",
            "10009",
            "10010",
            "20017",
            "538976598",
            "20001",
            "2101259",
            "2101260",
            "2101261",
        ]
        ordered = []
        for signal_id in preferred + list(realtime_signal_ids):
            if signal_id not in ordered:
                ordered.append(signal_id)
        return ordered

    def _extract_signal_values(self, payload):
        collected = {}

        def visit(node):
            if isinstance(node, dict):
                if "paramValues" in node and isinstance(node["paramValues"], dict):
                    collected.update(
                        {
                            str(reg_id): value
                            for reg_id, value in node["paramValues"].items()
                        }
                    )

                reg_id = (
                    node.get("id")
                    or node.get("signalId")
                    or node.get("signalID")
                    or node.get("signal_id")
                )
                has_value = any(
                    key in node
                    for key in ("value", "signalValue", "realValue", "currentValue", "val")
                )
                if reg_id is not None and has_value:
                    for key in ("value", "signalValue", "realValue", "currentValue", "val"):
                        if key in node:
                            collected[str(reg_id)] = node[key]
                            break

                for item in node.values():
                    visit(item)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        return collected

    def _extract_signal_catalog(self, payload):
        catalog = []

        def visit(node, group_name=None):
            if isinstance(node, dict):
                next_group = group_name
                if "groupName" in node and isinstance(node["groupName"], str):
                    next_group = node["groupName"]

                if "signals" in node and isinstance(node["signals"], list):
                    for signal in node["signals"]:
                        if not isinstance(signal, dict):
                            continue
                        signal_id = signal.get("id") or signal.get("signalId")
                        if signal_id is None:
                            continue
                        catalog.append(
                            {
                                "id": str(signal_id),
                                "name": signal.get("name"),
                                "unit": signal.get("unit"),
                                "group": next_group,
                            }
                        )

                for item in node.values():
                    visit(item, next_group)
            elif isinstance(node, list):
                for item in node:
                    visit(item, group_name)

        visit(payload)
        deduped = []
        seen = set()
        for item in catalog:
            key = (item["id"], item.get("name"), item.get("unit"), item.get("group"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _extract_signal_ids(self, payload):
        signal_ids = set()

        def visit(node):
            if isinstance(node, dict):
                for key in ("id", "signalId", "signalID", "signal_id"):
                    if key in node and node[key] is not None:
                        signal_ids.add(str(node[key]))
                for item in node.values():
                    visit(item)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        return signal_ids

    def _extract_config_signal_catalog(self, payload):
        catalog = []

        def visit(node):
            if isinstance(node, dict):
                signal_id = (
                    node.get("id")
                    or node.get("signalId")
                    or node.get("signalID")
                    or node.get("signal_id")
                )
                interesting_keys = {
                    "name",
                    "label",
                    "unit",
                    "value",
                    "realValue",
                    "defaultValue",
                    "rwFlag",
                    "readOnly",
                    "readonly",
                    "writable",
                    "writeable",
                    "min",
                    "max",
                    "minValue",
                    "maxValue",
                    "step",
                    "enumValues",
                    "options",
                    "optionList",
                    "range",
                }
                if signal_id is not None and any(key in node for key in interesting_keys):
                    catalog.append(
                        {
                            "id": str(signal_id),
                            "name": node.get("name") or node.get("label"),
                            "unit": node.get("unit"),
                            "value": node.get("value", node.get("realValue")),
                            "default": node.get("defaultValue"),
                            "writable": node.get("writable", node.get("writeable")),
                            "read_only": node.get("readOnly", node.get("readonly")),
                            "rw_flag": node.get("rwFlag"),
                            "min": node.get("min", node.get("minValue")),
                            "max": node.get("max", node.get("maxValue")),
                            "step": node.get("step"),
                            "options": node.get("options", node.get("optionList", node.get("enumValues"))),
                            "range": node.get("range"),
                        }
                    )

                for item in node.values():
                    visit(item)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        deduped = []
        seen = set()
        for item in catalog:
            key = (
                item["id"],
                item.get("name"),
                item.get("unit"),
                self._debug_repr(item.get("options")),
                item.get("min"),
                item.get("max"),
                item.get("rw_flag"),
                item.get("read_only"),
                item.get("writable"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _config_signal_values_from_catalog(self, signal_catalog):
        values = {}
        for item in signal_catalog:
            if item["id"] not in WRITABLE_REGISTERS:
                continue
            if item.get("value") is None:
                continue
            values[item["id"]] = item["value"]
        return values

    def _store_config_signal_details(self, signal_catalog):
        for item in signal_catalog:
            self.config_signal_details[item["id"]] = dict(item)

    def _log_realtime_signal_catalog(self, signal_catalog):
        catalog_key = tuple(
            (item["id"], item.get("name"), item.get("unit"), item.get("group"))
            for item in signal_catalog
        )
        if catalog_key == self._last_realtime_signal_catalog:
            return

        self._last_realtime_signal_catalog = catalog_key
        if not signal_catalog:
            self._debug_log("Wallbox realtime signal catalog is empty")
            return

        self._debug_log("Wallbox realtime signal catalog count=%s", len(signal_catalog))
        for item in signal_catalog:
            self._debug_log(
                "Wallbox realtime signal id=%s name=%s unit=%s group=%s",
                item["id"],
                item.get("name"),
                item.get("unit"),
                item.get("group"),
            )

    def _log_config_signal_catalog(self, operation, signal_catalog):
        catalog_key = tuple(
            (
                operation,
                item["id"],
                item.get("name"),
                item.get("unit"),
                item.get("value"),
                item.get("default"),
                item.get("writable"),
                item.get("read_only"),
                item.get("rw_flag"),
                item.get("min"),
                item.get("max"),
                item.get("step"),
                self._debug_repr(item.get("options")),
                self._debug_repr(item.get("range")),
            )
            for item in signal_catalog
        )
        if catalog_key == self._last_config_signal_catalog:
            return

        self._last_config_signal_catalog = catalog_key
        if not signal_catalog:
            self._debug_log("Wallbox config signal catalog is empty for %s", operation)
            return

        self._debug_log(
            "Wallbox config signal catalog count=%s operation=%s",
            len(signal_catalog),
            operation,
        )
        for item in signal_catalog:
            self._debug_log(
                "Wallbox config signal operation=%s id=%s name=%s unit=%s value=%s default=%s writable=%s read_only=%s rw_flag=%s min=%s max=%s step=%s options=%s range=%s",
                operation,
                item["id"],
                item.get("name"),
                item.get("unit"),
                item.get("value"),
                item.get("default"),
                item.get("writable"),
                item.get("read_only"),
                item.get("rw_flag"),
                item.get("min"),
                item.get("max"),
                item.get("step"),
                self._debug_repr(item.get("options")),
                self._debug_repr(item.get("range")),
            )

    def _convert_register_value(self, value):
        """Best-effort conversion for register payloads returned as strings."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return ""

            lowered = stripped.lower()
            if lowered in ("true", "false"):
                return lowered == "true"

            if _NUMERIC_PATTERN.match(stripped):
                if "." in stripped:
                    number = float(stripped)
                    return int(number) if number.is_integer() else number
                try:
                    return int(stripped)
                except ValueError:
                    return stripped

            return stripped

        return value

    def _normalize_host(self, value):
        if not value:
            return None

        raw = str(value).strip()
        if not raw:
            return None

        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        normalized = (parsed.hostname or parsed.netloc or raw).strip().lower()
        return normalized or None

    def _derive_locale(self):
        """Derive locale string for API payloads."""
        language = (self.hass.config.language or DEFAULT_LOCALE).replace("-", "_")
        if "_" in language:
            lang, _, region = language.partition("_")
            lang = lang or DEFAULT_LOCALE.split("_")[0]
            region = region or lang.upper()
            return f"{lang.lower()}_{region.upper()}"
        if len(language) == 2:
            return DEFAULT_LOCALE
        return DEFAULT_LOCALE

    def _derive_timezone_offset(self):
        """Return timezone offset in minutes."""
        timezone_name = self.hass.config.time_zone
        try:
            tzinfo = ZoneInfo(timezone_name) if timezone_name else None
        except Exception:
            tzinfo = None

        now = datetime.now(tzinfo) if tzinfo else datetime.now()
        offset = now.utcoffset()
        if offset is None:
            return DEFAULT_TIMEZONE_OFFSET
        return int(offset.total_seconds() / 60)

    def _reset_auth_state(self):
        """Clear auth-related state so the next request authenticates again."""
        self.token = None
        self.headers = {}
        self.region_ip = None
        self.dn_id = None
        self.wallbox_dn = None
        self.wallbox_dn_id = None
        self.config_signal_details = {}
        self.config_signal_values = {}
        self._last_realtime_signal_catalog = None
        self._last_config_signal_catalog = None
        self._history_probe_completed = False

    def _ensure_device_context(self):
        """Ensure authentication and target device identifiers are available."""
        if not self.token or not self.region_ip or not self.headers:
            self.authenticate()
        elif not self.dn_id:
            self.fetch_station_dn()

    def get_register_value(self, reg_id):
        reg_id = str(reg_id)
        if reg_id in self.param_values:
            return self.param_values[reg_id]
        return self.config_signal_values.get(reg_id)

    def _build_debug_data(self):
        return {
            "last_update_status": "idle",
            "last_update_error": None,
            "last_update_at": None,
            "last_update_duration_ms": None,
            "last_update_response_excerpt": None,
            "last_register_count": 0,
            "available_registers": [],
            "writable_registers_available": [],
            "missing_writable_registers": list(WRITABLE_REGISTERS),
            "last_write_status": "idle",
            "last_write_param_id": None,
            "last_write_value": None,
            "last_write_error": None,
            "last_write_at": None,
            "last_write_duration_ms": None,
            "last_write_attempts": 0,
            "last_write_response_excerpt": None,
        }

    def is_reauth_required(self):
        """Return True when the latest error indicates credentials were rejected."""
        return self._error_requires_reauth(self.debug_data.get("last_update_error")) or self._error_requires_reauth(
            self.debug_data.get("last_write_error")
        )

    def _error_requires_reauth(self, error):
        if not isinstance(error, str):
            return False

        lowered = error.lower()
        reauth_markers = (
            "authentication error",
            "invalid username or password",
            "reauth",
            "http 401",
            "http 403",
        )
        return any(marker in lowered for marker in reauth_markers)

    def _update_register_debug_state(self):
        self._ensure_debug_data()
        available_registers = sorted(
            {str(reg_id) for reg_id in self.param_values.keys()}.union(self.config_signal_values.keys())
        )
        writable_available = [reg_id for reg_id in WRITABLE_REGISTERS if reg_id in available_registers]

        self.debug_data.update(
            {
                "last_register_count": len(available_registers),
                "available_registers": available_registers,
                "writable_registers_available": writable_available,
                "missing_writable_registers": [reg_id for reg_id in WRITABLE_REGISTERS if reg_id not in available_registers],
            }
        )
        self._schedule_debug_state_push()

    def _clear_register_debug_state(self):
        self._ensure_debug_data()
        self.debug_data.update(
            {
                "last_register_count": 0,
                "available_registers": [],
                "writable_registers_available": [],
                "missing_writable_registers": list(WRITABLE_REGISTERS),
            }
        )
        self._schedule_debug_state_push()

    def _record_update_debug(self, *, status, error=None, duration_ms=None, response_excerpt=None):
        self._ensure_debug_data()
        self.debug_data.update(
            {
                "last_update_status": status,
                "last_update_error": error,
                "last_update_at": self._utc_timestamp(),
                "last_update_duration_ms": duration_ms,
                "last_update_response_excerpt": response_excerpt,
            }
        )
        self._schedule_debug_state_push()

    def _record_write_debug(
        self,
        *,
        status,
        param_id,
        value,
        error=None,
        attempts=None,
        duration_ms=None,
        response_excerpt=None,
    ):
        self._ensure_debug_data()
        self.debug_data.update(
            {
                "last_write_status": status,
                "last_write_param_id": str(param_id) if param_id is not None else None,
                "last_write_value": value,
                "last_write_error": error,
                "last_write_at": self._utc_timestamp(),
                "last_write_duration_ms": duration_ms,
                "last_write_attempts": attempts if attempts is not None else self.debug_data.get("last_write_attempts", 0),
                "last_write_response_excerpt": response_excerpt,
            }
        )
        self._schedule_debug_state_push()

    def _ensure_debug_data(self):
        if not hasattr(self, "debug_data"):
            self.debug_data = self._build_debug_data()

    def _debug_log(self, message, *args):
        if getattr(self, "enable_logging", True):
            _LOGGER.warning(message, *args)

    def _schedule_debug_state_push(self):
        loop = getattr(self.hass, "loop", None)
        if loop is None:
            return

        current_data = getattr(self, "data", self.param_values)
        loop.call_soon_threadsafe(self.async_set_updated_data, current_data)

    def _debug_repr(self, value):
        return self._truncate_text(self._sanitize_debug_value(value))

    def _sanitize_debug_value(self, value):
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                lower_key = str(key).lower()
                if lower_key in {
                    "password",
                    "value",
                    "accesstoken",
                    "refreshtoken",
                    "token",
                    "cookie",
                    "set-cookie",
                    "authorization",
                    "bspsession",
                    "dp-session",
                    "csrftoken",
                    "csrf-token",
                    "roarand",
                }:
                    sanitized[key] = "***"
                else:
                    sanitized[key] = self._sanitize_debug_value(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_debug_value(item) for item in value]
        return value

    def _truncate_text(self, value, limit=500):
        if value is None:
            return None
        if not isinstance(value, str):
            try:
                value = json.dumps(value, sort_keys=True)
            except TypeError:
                value = str(value)
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def _json_dump(self, value):
        try:
            return self._truncate_text(json.dumps(self._sanitize_debug_value(value), sort_keys=True))
        except TypeError:
            return self._truncate_text(str(self._sanitize_debug_value(value)))

    def _response_excerpt(self, response):
        if response is None:
            return None

        try:
            return self._json_dump(response.json())
        except ValueError:
            return self._truncate_text(self._sanitize_text(getattr(response, "text", None)))

    def _response_headers_excerpt(self, response):
        if response is None:
            return None
        try:
            return self._debug_repr(dict(response.headers))
        except Exception:
            return None

    def _sanitize_text(self, value):
        if not isinstance(value, str):
            return value

        sanitized = value
        replacements = (
            (r'("accessToken"\s*:\s*")[^"]+(")', r'\1***\2'),
            (r'("refreshToken"\s*:\s*")[^"]+(")', r'\1***\2'),
            (r'("token"\s*:\s*")[^"]+(")', r'\1***\2'),
            (r'("roaRand"\s*:\s*")[^"]+(")', r'\1***\2'),
            (r'("csrfToken"\s*:\s*")[^"]+(")', r'\1***\2'),
            (r'(bspsession=)[^;"]+', r'\1***'),
            (r'(dp-session=)[^;"]+', r'\1***'),
        )
        for pattern, replacement in replacements:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized

    def _elapsed_ms(self, started):
        return round((time.monotonic() - started) * 1000)

    def _utc_timestamp(self):
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
