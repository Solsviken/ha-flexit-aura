"""The Flexit Aura integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant

from .client import AuraClient
from .const import CONF_DEVICE_ID, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL
from .coordinator import FlexitAuraConfigEntry, FlexitAuraCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: FlexitAuraConfigEntry) -> bool:
    """Set up one ventilation unit from a config entry."""
    client = AuraClient(
        host=entry.data[CONF_HOST],
        device_id=entry.data[CONF_DEVICE_ID],
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = FlexitAuraCoordinator(hass, entry, client, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlexitAuraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: FlexitAuraConfigEntry) -> None:
    """Reload when the poll interval is changed in the options flow."""
    await hass.config_entries.async_reload(entry.entry_id)
