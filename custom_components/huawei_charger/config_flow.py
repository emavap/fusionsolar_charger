from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import voluptuous as vol

from .const import DOMAIN, CONF_INTERVAL

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_INTERVAL, default=30): int,
})

class HuaweiChargerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_reauth(self, user_input=None):
        if user_input is not None:
            existing_entry = next(
                entry for entry in self._async_current_entries()
                if entry.data[CONF_USERNAME] == user_input[CONF_USERNAME]
            )
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(step_id="reauth", data_schema=DATA_SCHEMA)