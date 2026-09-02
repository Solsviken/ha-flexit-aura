"""Fan entity: power and the three verified speed steps."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import ORDERED_SPEEDS, REG_POWER, REG_SPEED
from .coordinator import FlexitAuraConfigEntry, FlexitAuraCoordinator
from .entity import FlexitAuraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitAuraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([FlexitAuraFan(entry.runtime_data)])


class FlexitAuraFan(FlexitAuraEntity, FanEntity):
    """Maps the unit's 1/2/3 speed steps onto Home Assistant percentages."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(ORDERED_SPEEDS)

    def __init__(self, coordinator: FlexitAuraCoordinator) -> None:
        super().__init__(coordinator, "fan")

    @property
    def is_on(self) -> bool | None:
        power = self.coordinator.data.power
        return None if power is None else power == 1

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        if data.power == 0:
            return 0
        speed = data.speed
        if speed not in ORDERED_SPEEDS:
            # Standby (0) and manual (255) have no percentage equivalent.
            return None
        return ordered_list_item_to_percentage(ORDERED_SPEEDS, speed)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.coordinator.async_write(REG_POWER, 0)
            return
        speed = percentage_to_ordered_list_item(ORDERED_SPEEDS, percentage)
        await self.coordinator.async_write(REG_SPEED, speed)
        if self.coordinator.data.power != 1:
            await self.coordinator.async_write(REG_POWER, 1)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self.coordinator.async_write(REG_POWER, 1)
        if percentage:
            speed = percentage_to_ordered_list_item(ORDERED_SPEEDS, percentage)
            await self.coordinator.async_write(REG_SPEED, speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(REG_POWER, 0)
