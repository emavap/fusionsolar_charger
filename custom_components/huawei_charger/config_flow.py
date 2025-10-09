from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol
import logging
import requests

from .const import DOMAIN, CONF_INTERVAL, DEFAULT_REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_INTERVAL, default=30): int,
    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
})

class HuaweiChargerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HuaweiChargerOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                # Validate credentials
                await self.hass.async_add_executor_job(
                    self._validate_credentials,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_VERIFY_SSL],
                )
                # Create entry if validation succeeds
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
            except InvalidCredentials:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"
                
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)
    
    def _validate_credentials(self, username: str, password: str, verify_ssl: bool):
        """Validate credentials by attempting authentication."""
        url = "https://intl.fusionsolar.huawei.com:32800/rest/neteco/appauthen/v1/smapp/app/token"
        payload = {
            "userName": username,
            "value": password,
            "grantType": "password",
            "verifyCode": "",
            "appClientId": "86366133-B8B5-41FA-8EB9-E5A64229E3E1"
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                verify=verify_ssl,
                headers={"Content-Type": "application/json"},
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if "data" not in data or "accessToken" not in data["data"]:
                raise InvalidCredentials("Invalid authentication response")

        except requests.exceptions.Timeout as err:
            raise CannotConnect("Connection timeout") from err
        except requests.exceptions.ConnectionError as err:
            raise CannotConnect("Connection failed") from err
        except requests.exceptions.HTTPError as err:
            if err.response is not None and err.response.status_code in [401, 403]:
                raise InvalidCredentials("Invalid username or password") from err
            raise CannotConnect(f"HTTP error: {err.response.status_code if err.response else 'unknown'}") from err
        except requests.exceptions.SSLError as err:
            if verify_ssl:
                raise CannotConnect("SSL validation failed") from err
            raise CannotConnect("SSL handshake failed") from err
        except ValueError as err:
            raise CannotConnect("Invalid response payload") from err
        except Exception as err:
            _LOGGER.error("Validation error: %s", err)
            raise CannotConnect("Unknown connection error") from err

    async def async_step_reauth(self, user_input=None):
        if user_input is not None:
            existing_entry = next(
                entry for entry in self._async_current_entries()
                if entry.data[CONF_USERNAME] == user_input[CONF_USERNAME]
            )
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(step_id="reauth", data_schema=DATA_SCHEMA)


class InvalidCredentials(HomeAssistantError):
    """Error to indicate invalid credentials."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class HuaweiChargerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Huawei Charger."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input}
            )
            return self.async_create_entry(title="", data={})

        # Get current values
        current_interval = self.config_entry.data.get(CONF_INTERVAL, 30)
        current_verify_ssl = self.config_entry.data.get(CONF_VERIFY_SSL, False)

        options_schema = vol.Schema({
            vol.Optional(CONF_INTERVAL, default=current_interval): int,
            vol.Optional(CONF_VERIFY_SSL, default=current_verify_ssl): bool,
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)
