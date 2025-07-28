import logging
from datetime import timedelta
import requests
import urllib3
import asyncio
import time
import json

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_INTERVAL

_LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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

        self.token = None
        self.headers = {}
        self.region_ip = None
        self.dn_id = None
        self.wallbox_dn_id = None
        self.param_values = {}

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
        response = requests.post(url, json=payload, verify=False, headers={"Content-Type": "application/json"})
        data = response.json()
        if "data" in data and "accessToken" in data["data"]:
            self.token = data["data"]["accessToken"]
            self.region_ip = data["data"]["regionFloatIp"]
            self.headers = {
                'roaRand': data["data"]["roaRand"],
                'Cookie': f"locale=de-de;bspsession={self.token};dp-session={self.token}; Secure; HttpOnly",
                'Content-Type': 'application/json',
                'x-timezone-offset': '120',
                'User-Agent': 'iCleanPower/24.6.102006'
            }
            self.fetch_station_dn()

    def fetch_station_dn(self):
        url = f"https://{self.region_ip}:32800/rest/pvms/web/station/v1/station/station-list"
        payload = {
            "locale": "de_DE",
            "sortId": "createTime",
            "timeZone": "2.00",
            "pageSize": "11",
            "supportMDevice": "1",
            "sortDir": "DESC",
            "curPage": 1
        }
        response = requests.post(url, json=payload, headers=self.headers, verify=False)
        response.raise_for_status()
        data = response.json()
        
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

        response = requests.post(url, data=payload, headers=headers, verify=False)
        response.raise_for_status()

        try:
            data = response.json()
            _LOGGER.debug("Full wallbox fetch response:\n%s", json.dumps(data, indent=2))
        except Exception:
            _LOGGER.warning("Wallbox response could not be parsed as JSON.")
            return {}

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
                response = requests.post(url, json=payload, headers=headers, verify=False)
                try:
                    data = response.json()
                    _LOGGER.debug("Set config response JSON:\n%s", json.dumps(data, indent=2))
                except Exception:
                    _LOGGER.warning(f"Set config response for param {param_id} -> {value}: Response body was not valid JSON.")
                response.raise_for_status()
                if response.status_code == 200:
                    _LOGGER.info(f"Successfully set config {param_id} to {value}")
                    return True
            except requests.RequestException as err:
                _LOGGER.warning(f"Set config attempt {attempt + 1}/{retries} failed: {err}")

            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                _LOGGER.error(f"Failed to set config {param_id} after {retries} attempts")

        return False
