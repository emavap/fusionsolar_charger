import logging
from urllib.parse import urlparse

import requests
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_ENABLE_LOGGING,
    CONF_INTERVAL,
    DEFAULT_ENABLE_LOGGING,
    DEFAULT_FUSIONSOLAR_HOST,
    DEFAULT_REQUEST_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_INTERVAL = 30
APP_TOKEN_PATH = "/rest/neteco/appauthen/v1/smapp/app/token"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST, default=DEFAULT_FUSIONSOLAR_HOST): str,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        vol.Optional(CONF_ENABLE_LOGGING, default=DEFAULT_ENABLE_LOGGING): bool,
    }
)


class HuaweiChargerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def _coerce_bool(value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "on", "yes"}:
                return True
            if normalized in {"0", "false", "off", "no", ""}:
                return False
        return bool(value)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HuaweiChargerOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                host = self._normalize_host(user_input[CONF_HOST])
                username = user_input[CONF_USERNAME].strip()
                await self.async_set_unique_id(self._build_unique_id(username, host))
                self._abort_if_unique_id_configured()

                await self.hass.async_add_executor_job(
                    self._validate_credentials,
                    host,
                    username,
                    user_input[CONF_PASSWORD],
                    user_input[CONF_VERIFY_SSL],
                )

                options = {
                    CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                    CONF_VERIFY_SSL: self._coerce_bool(
                        user_input.get(CONF_VERIFY_SSL),
                        False,
                    ),
                    CONF_ENABLE_LOGGING: self._coerce_bool(
                        user_input.get(CONF_ENABLE_LOGGING),
                        DEFAULT_ENABLE_LOGGING,
                    ),
                }
                entry_data = {
                    CONF_USERNAME: username,
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_HOST: host,
                }
                return self.async_create_entry(
                    title=self._build_title(username, host),
                    data=entry_data,
                    options=options,
                )
            except InvalidCredentials:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_reauth(self, user_input=None):
        entry = self._get_linked_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None and not self._is_reauth_submission(user_input):
            user_input = None

        if user_input is not None:
            try:
                host = self._normalize_host(user_input[CONF_HOST])
                username = user_input[CONF_USERNAME].strip()
                unique_id = self._build_unique_id(username, host)
                await self.async_set_unique_id(unique_id)
                if self._has_conflicting_entry(unique_id, entry.entry_id):
                    return self.async_abort(reason="already_configured")

                verify_ssl = entry.options.get(
                    CONF_VERIFY_SSL,
                    entry.data.get(CONF_VERIFY_SSL, False),
                )
                await self.hass.async_add_executor_job(
                    self._validate_credentials,
                    host,
                    username,
                    user_input[CONF_PASSWORD],
                    verify_ssl,
                )

                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=self._build_title(username, host),
                    data={
                        **entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_HOST: host,
                    },
                    reason="reauth_successful",
                )
            except InvalidCredentials:
                return self.async_show_form(
                    step_id="reauth",
                    data_schema=self._reauth_schema(entry),
                    errors={"base": "invalid_auth"},
                )
            except CannotConnect:
                return self.async_show_form(
                    step_id="reauth",
                    data_schema=self._reauth_schema(entry),
                    errors={"base": "cannot_connect"},
                )
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                return self.async_show_form(
                    step_id="reauth",
                    data_schema=self._reauth_schema(entry),
                    errors={"base": "unknown"},
                )

        return self.async_show_form(
            step_id="reauth",
            data_schema=self._reauth_schema(entry),
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_linked_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            host = self._normalize_host(user_input[CONF_HOST])
            username = entry.data.get(CONF_USERNAME, "")
            unique_id = self._build_unique_id(username, host)
            await self.async_set_unique_id(unique_id)
            if self._has_conflicting_entry(unique_id, entry.entry_id):
                return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry,
                unique_id=unique_id,
                title=self._build_title(username, host),
                data={**entry.data, CONF_HOST: host},
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=entry.data.get(CONF_HOST, DEFAULT_FUSIONSOLAR_HOST),
                    ): str
                }
            ),
        )

    def _reauth_schema(self, entry):
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                ): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_HOST, default=entry.data.get(CONF_HOST, DEFAULT_FUSIONSOLAR_HOST)
                ): str,
            }
        )

    def _get_linked_entry(self):
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return None
        return self.hass.config_entries.async_get_entry(entry_id)

    def _has_conflicting_entry(self, unique_id: str, current_entry_id: str | None) -> bool:
        for entry in self._async_current_entries():
            if entry.entry_id == current_entry_id:
                continue
            if entry.unique_id == unique_id:
                return True
        return False

    @staticmethod
    def _is_reauth_submission(user_input) -> bool:
        return isinstance(user_input, dict) and all(
            field in user_input for field in (CONF_USERNAME, CONF_PASSWORD, CONF_HOST)
        )

    def _validate_credentials(self, host: str, username: str, password: str, verify_ssl: bool):
        """Validate credentials by attempting authentication."""
        payload = {
            "userName": username,
            "value": password,
            "grantType": "password",
            "verifyCode": "",
            "appClientId": "86366133-B8B5-41FA-8EB9-E5A64229E3E1",
        }

        try:
            for candidate_host in self._authentication_hosts(host):
                response = requests.post(
                    self._app_token_url(candidate_host),
                    json=payload,
                    verify=verify_ssl,
                    headers={"Content-Type": "application/json"},
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()

                token_data = data.get("data") or {}
                if token_data.get("accessToken") or token_data.get("token"):
                    return

            raise CannotConnect("Authentication response missing access token")

        except requests.exceptions.Timeout as err:
            raise CannotConnect("Connection timeout") from err
        except requests.exceptions.ConnectionError as err:
            raise CannotConnect("Connection failed") from err
        except requests.exceptions.HTTPError as err:
            if err.response is not None and err.response.status_code in [401, 403]:
                raise InvalidCredentials("Invalid username or password") from err
            raise CannotConnect(
                f"HTTP error: {err.response.status_code if err.response else 'unknown'}"
            ) from err
        except requests.exceptions.SSLError as err:
            if verify_ssl:
                raise CannotConnect("SSL validation failed") from err
            raise CannotConnect("SSL handshake failed") from err
        except ValueError as err:
            raise CannotConnect("Invalid response payload") from err
        except Exception as err:
            _LOGGER.error("Validation error: %s", err)
            raise CannotConnect("Unknown connection error") from err

    @staticmethod
    def _normalize_host(host: str) -> str:
        """Accept a hostname or full FusionSolar URL and return the host only."""
        raw = (host or "").strip()
        if not raw:
            return DEFAULT_FUSIONSOLAR_HOST

        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        normalized = (parsed.hostname or parsed.netloc or raw).strip().lower()
        if not normalized:
            return DEFAULT_FUSIONSOLAR_HOST
        return normalized

    @staticmethod
    def _build_unique_id(username: str, host: str) -> str:
        return f"{username.lower()}@{host.lower()}"

    @staticmethod
    def _build_title(username: str, host: str) -> str:
        return f"{username} @ {host}"

    @staticmethod
    def _authentication_hosts(host: str) -> list[str]:
        hosts = [host]
        if host != DEFAULT_FUSIONSOLAR_HOST:
            hosts.append(DEFAULT_FUSIONSOLAR_HOST)
        return hosts

    @staticmethod
    def _app_token_url(host: str) -> str:
        return f"https://{host}:32800{APP_TOKEN_PATH}"


class InvalidCredentials(HomeAssistantError):
    """Error to indicate invalid credentials."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class HuaweiChargerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Huawei Charger."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        entry = self._get_config_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            try:
                host = HuaweiChargerConfigFlow._normalize_host(user_input[CONF_HOST])
                username = entry.data.get(CONF_USERNAME, "")
                unique_id = (
                    HuaweiChargerConfigFlow._build_unique_id(username, host)
                    if username
                    else entry.unique_id
                )
                if unique_id and self._has_conflicting_entry(unique_id, entry.entry_id):
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._options_schema(entry),
                        errors={"base": "already_configured"},
                    )

                validated = {
                    CONF_INTERVAL: user_input.get(
                        CONF_INTERVAL,
                        entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                    ),
                    CONF_VERIFY_SSL: HuaweiChargerConfigFlow._coerce_bool(
                        user_input.get(CONF_VERIFY_SSL),
                        False,
                    ),
                    CONF_ENABLE_LOGGING: HuaweiChargerConfigFlow._coerce_bool(
                        user_input.get(CONF_ENABLE_LOGGING),
                        False,
                    ),
                }
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_HOST: host},
                    options={**entry.options, **validated},
                    title=HuaweiChargerConfigFlow._build_title(username, host),
                    unique_id=unique_id,
                )
                return self.async_create_entry(title="", data={})
            except Exception:
                _LOGGER.exception("Unexpected error while updating options")
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._options_schema(entry),
                    errors={"base": "unknown"},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(entry),
        )

    def _options_schema(self, entry):
        current_interval = entry.options.get(
            CONF_INTERVAL,
            entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL),
        )
        current_verify_ssl = entry.options.get(
            CONF_VERIFY_SSL,
            entry.data.get(CONF_VERIFY_SSL, False),
        )
        current_host = entry.data.get(CONF_HOST, DEFAULT_FUSIONSOLAR_HOST)
        current_enable_logging = entry.options.get(
            CONF_ENABLE_LOGGING,
            entry.data.get(CONF_ENABLE_LOGGING, DEFAULT_ENABLE_LOGGING),
        )

        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_INTERVAL, default=current_interval): vol.All(
                    int, vol.Range(min=10, max=3600)
                ),
                vol.Required(CONF_VERIFY_SSL, default=current_verify_ssl): bool,
                vol.Required(CONF_ENABLE_LOGGING, default=current_enable_logging): bool,
            }
        )

    def _get_config_entry(self):
        config_entry = getattr(self, "config_entry", None)
        if config_entry is not None:
            return config_entry

        entry_id = self.context.get("entry_id") if hasattr(self, "context") else None
        if entry_id:
            return self.hass.config_entries.async_get_entry(entry_id)

        handler = getattr(self, "handler", None)
        if handler:
            return self.hass.config_entries.async_get_entry(handler)

        return None

    def _has_conflicting_entry(self, unique_id: str, current_entry_id: str) -> bool:
        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
            if config_entry.entry_id == current_entry_id:
                continue
            if config_entry.unique_id == unique_id:
                return True
        return False
