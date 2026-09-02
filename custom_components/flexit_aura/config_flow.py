"""Config and options flow for the Flexit Aura integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import AuraAuthError, AuraClient, AuraConnectionError, AuraError
from .const import (
    CONF_DEVICE_ID,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    POLL_REGISTERS,
)
from .coordinator import FlexitAuraConfigEntry

# The unit answers nothing at all when the device ID does not match, so there is
# no discovery to fall back on and the ID has to be entered.
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default="Flexit Aura"): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class FlexitAuraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the unit's address and confirm we can talk to it."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            device_id = user_input[CONF_DEVICE_ID].strip().upper()
            password = user_input[CONF_PASSWORD].strip()
            port = user_input[CONF_PORT]

            client = AuraClient(
                host=host, device_id=device_id, password=password, port=port
            )
            try:
                await client.async_read(POLL_REGISTERS)
            except AuraAuthError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except AuraConnectionError:
                # Covers both an unreachable unit and a wrong device ID, which
                # the unit answers with silence rather than an error frame.
                errors["base"] = "cannot_connect"
            except AuraError:
                errors["base"] = "unknown_response"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_DEVICE_ID: device_id,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: FlexitAuraConfigEntry) -> OptionsFlow:
        return FlexitAuraOptionsFlow()


class FlexitAuraOptionsFlow(OptionsFlow):
    """Only the poll interval is adjustable after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
