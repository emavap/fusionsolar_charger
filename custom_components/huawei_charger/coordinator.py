import logging
from datetime import timedelta
import requests
import urllib3
import time

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_INTERVAL

_LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class HuaweiChargerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.username = entry.data.get("username")
        self.password = entry.data.get("password")
        self.interval = entry.data.get(CONF_INTERVAL, 30)

        self.token = None
        self.headers = {}
        self.region_ip = None
        self.dn_id = None
        self.wallbox_dn_id = None
        self.param_values = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.interval),
        )

    async def _async_update_data(self):
        retries = 3
        for attempt in range(retries):
            try:
                if not self.token:
                    await self.hass.async_add_executor_job(self.authenticate)

                await self.hass.async_add_executor_job(self.fetch_wallbox_info)
                return self.param_values
            except requests.RequestException as err:
                _LOGGER.warning(f"Attempt {attempt+1}/{retries} failed: {err}")
                if attempt < retries - 1:
                    sleep_time = 2 ** attempt
                    _LOGGER.info(f"Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    self.token = None  # reset token to force re-authentication
                else:
                    raise UpdateFailed(f"Failed after retries: {err}") from err

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
        response.raise_for_status()
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
        else:
            raise UpdateFailed("Authentication failed")

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
        self.dn_id = data["data"]["list"][0]["dn"]

    def fetch_wallbox_info(self):
        payload = f"conditionParams.curPage=0&conditionParams.mocTypes=60080&conditionParams.parentDn={self.dn_id}&conditionParams.recordperpage=500"
        url = f"https://{self.region_ip}:32800/rest/neteco/web/config/device/v1/device-list"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        response = requests.post(url, data=payload, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()
        wallbox = data["data"][0]
        self.wallbox_dn_id = wallbox["dnId"]
        self.param_values = wallbox.get("paramValues", {})
