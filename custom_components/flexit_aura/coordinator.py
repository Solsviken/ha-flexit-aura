"""Polling coordinator for the Flexit Aura."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuraClient, AuraError
from .const import DOMAIN, POLL_REGISTERS
from .model import FlexitAuraData

_LOGGER = logging.getLogger(__name__)

type FlexitAuraConfigEntry = ConfigEntry[FlexitAuraCoordinator]


class FlexitAuraCoordinator(DataUpdateCoordinator[FlexitAuraData]):
    """Reads every register in one datagram per interval."""

    config_entry: FlexitAuraConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FlexitAuraConfigEntry,
        client: AuraClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {client.host}",
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> FlexitAuraData:
        try:
            values = await self.client.async_read(POLL_REGISTERS)
        except AuraError as err:
            raise UpdateFailed(str(err)) from err
        return FlexitAuraData.from_parameters(values)

    async def async_write(self, register: int, value: int) -> None:
        """Write, then refresh so every entity reflects the confirmed state."""
        await self.client.async_write(register, value)
        await self.async_request_refresh()
