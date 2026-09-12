"""Polling coordinator for the Flexit Aura."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuraClient, AuraError
from .const import DOMAIN, MAX_CONSECUTIVE_FAILURES, POLL_REGISTERS
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
        self.consecutive_failures = 0

    async def _async_update_data(self) -> FlexitAuraData:
        try:
            values = await self.client.async_read(POLL_REGISTERS)
        except AuraError as err:
            self.consecutive_failures += 1
            # A single missed poll shows up in Home Assistant as every entity
            # flipping to unavailable for exactly one interval. Seen on
            # 2026-09-12 as nine 30-second blips in ten hours on a unit that was
            # fine the whole time. Keep the last snapshot until the unit has
            # missed several polls in a row.
            if (
                self.data is not None
                and self.consecutive_failures < MAX_CONSECUTIVE_FAILURES
            ):
                _LOGGER.debug(
                    "Poll %s/%s mot %s feilet, beholder forrige data: %s",
                    self.consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                    self.client.host,
                    err,
                )
                return self.data
            raise UpdateFailed(str(err)) from err
        self.consecutive_failures = 0
        return FlexitAuraData.from_parameters(values)

    async def async_write(self, register: int, value: int) -> None:
        """Write, then refresh so every entity reflects the confirmed state."""
        await self.client.async_write(register, value)
        await self.async_request_refresh()
