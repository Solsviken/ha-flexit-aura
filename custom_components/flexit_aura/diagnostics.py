"""Diagnostics for the Flexit Aura integration.

The raw register dump is the fastest way to check a decoding assumption
against what the physical unit actually returned.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID
from .coordinator import FlexitAuraConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_DEVICE_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FlexitAuraConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT),
            "options": dict(entry.options),
            "redacted": sorted(TO_REDACT),
        },
        "last_update_success": coordinator.last_update_success,
        "decoded": asdict(data) if data else None,
    }
