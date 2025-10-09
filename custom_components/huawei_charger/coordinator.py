import logging
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import requests
import asyncio
import time
import json

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    CONF_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE_OFFSET,
)

_LOGGER = logging.getLogger(__name__)


class HuaweiChargerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data.get(CONF_INTERVAL, 30)),
        )
        self.hass = hass
        self.entry = entry
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
        self.request_timeout = DEFAULT_REQUEST_TIMEOUT

        self.token = None
        self.headers = {}
        self.region_ip = None
        self.dn_id = None
        self.wallbox_dn_id = None
        self.param_values = {}
        self.locale = self._derive_locale()
        self.timezone_offset = self._derive_timezone_offset()

    async def _async_update_data(self):
        for attempt in range(3):
            try:
                if not self.token:
                    await self.hass.async_add_executor_job(self.authenticate)

                await self.hass.async_add_executor_job(self.fetch_wallbox_info)
                return self.param_values

            except Exception as err:
                _LOGGER.warning(f"Update attempt {attempt + 1}/3 failed: {err}")
                self.token = None
                self.headers = {}
                self.region_ip = None
                self.dn_id = None
                self.wallbox_dn_id = None

                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise UpdateFailed(f"Update failed after retries: {err}") from err

    def authenticate(self):
        url = "https://intl.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token"
        payload = {
            "userName": self.username,
            "value": self.password,
            "grantType": "password",
            "verifyCode": "",
            "appClientId": "86366133-B8B5-41FA-8EB9-E5A64229E3E1"
        }
        response = self._request_post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        data = self._json_or_error(response, "authenticate")

        token_data = data.get("data") or {}
        if not token_data or "accessToken" not in token_data or "regionFloatIp" not in token_data:
            raise UpdateFailed("Authentication response missing expected fields")

        self.token = token_data["accessToken"]
        self.region_ip = token_data["regionFloatIp"]
        roa_rand = token_data.get("roaRand")

        cookie_locale = self.locale.replace("_", "-").lower()
        self.headers = {
            "roaRand": roa_rand,
            "Cookie": f"locale={cookie_locale};bspsession={self.token};dp-session={self.token}; Secure; HttpOnly",
            "Content-Type": "application/json",
            "x-timezone-offset": str(self.timezone_offset),
            "User-Agent": "iCleanPower/24.6.102006",
        }

        self.fetch_station_dn()

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
        response = self._request_post(url, json=payload, headers=self.headers)
        data = self._json_or_error(response, "station-list")
        
        if not data.get("data", {}).get("list"):
            raise ValueError("No stations found in account")
        
        self.dn_id = data["data"]["list"][0]["dn"]

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

        response = self._request_post(url, data=payload, headers=headers)

        data = self._json_or_error(response, "wallbox-info", default={})
        _LOGGER.debug("Full wallbox fetch response:\n%s", json.dumps(data, indent=2))

        if not data.get("data") or not isinstance(data["data"], list) or len(data["data"]) == 0:
            raise ValueError("No wallbox devices found in station")
            
        wallbox = data["data"][0]
        self.wallbox_dn_id = wallbox["dnId"]
        self.param_values = wallbox.get("paramValues", {})
        
        # Log available register IDs for debugging
        if self.param_values:
            available_registers = list(self.param_values.keys())
            _LOGGER.info("Available register IDs from charger: %s", sorted(available_registers))
            
            # Log some key values for debugging (using confirmed registers)
            key_registers = ["20001", "538976598", "10009", "10010", "20012", "20017"]
            for reg_id in key_registers:
                if reg_id in self.param_values:
                    _LOGGER.debug("Register %s value: %s", reg_id, self.param_values[reg_id])
        
        return self.param_values

    def set_config_value(self, param_id: str, value, retries=3):
        url = f"https://{self.region_ip}:32800/rest/neteco/web/homemgr/v1/device/set-config-info"
        payload = {
            "dnId": self.wallbox_dn_id,
            "changeValues": [{"id": int(param_id), "value": value}]
        }
        headers = self.headers.copy()

        for attempt in range(retries):
            try:
                response = self._request_post(url, json=payload, headers=headers)
                data = self._json_or_error(response, f"set-config-{param_id}", default={})
                _LOGGER.debug("Set config response JSON:\n%s", json.dumps(data, indent=2))
                if response.status_code == 200:
                    _LOGGER.info("Successfully set config %s to %s", param_id, value)
                    return True
            except UpdateFailed as err:
                _LOGGER.warning("Set config attempt %s/%s failed: %s", attempt + 1, retries, err)
            except requests.RequestException as err:
                _LOGGER.warning("Set config attempt %s/%s failed: %s", attempt + 1, retries, err)

            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                _LOGGER.error("Failed to set config %s after %s attempts", param_id, retries)

        return False

    def _request_post(self, url, *, json=None, data=None, headers=None):
        """Wrapper for POST requests with shared settings."""
        try:
            response = requests.post(
                url,
                json=json,
                data=data,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.request_timeout,
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
            raise UpdateFailed(f"HTTP {status} error while contacting FusionSolar API") from err

    def _json_or_error(self, response, context, default=None):
        """Parse JSON or raise an UpdateFailed."""
        try:
            return response.json()
        except ValueError as err:
            if default is not None:
                _LOGGER.warning("Response for %s was not JSON: %s", context, err)
                return default
            raise UpdateFailed(f"Invalid JSON response during {context}") from err

    def _derive_locale(self):
        """Derive locale string for API payloads. Defaults to German for compatibility."""
        return DEFAULT_LOCALE

    def _derive_timezone_offset(self):
        """Return timezone offset in minutes. Defaults to +2:00 (CEST) for compatibility."""
        return DEFAULT_TIMEZONE_OFFSET
