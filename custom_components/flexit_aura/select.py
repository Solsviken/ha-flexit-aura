"""Air mode select for the Flexit Aura (register 0xB7)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AIR_MODE_VALUES, AIR_MODES, REG_AIR_MODE
from .coordinator import FlexitAuraConfigEntry, FlexitAuraCoordinator
from .entity import FlexitAuraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitAuraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([FlexitAuraAirModeSelect(entry.runtime_data)])


class FlexitAuraAirModeSelect(FlexitAuraEntity, SelectEntity):
    """Ventilation, heat recovery or supply-only air flow."""

    _attr_translation_key = "air_mode"
    _attr_options = list(AIR_MODES.values())

    def __init__(self, coordinator: FlexitAuraCoordinator) -> None:
        super().__init__(coordinator, "air_mode")

    @property
    def current_option(self) -> str | None:
        return AIR_MODES.get(self.coordinator.data.air_mode)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(REG_AIR_MODE, AIR_MODE_VALUES[option])
