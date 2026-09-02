"""Alarm, filter and status flags for the Flexit Aura."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlexitAuraConfigEntry, FlexitAuraCoordinator
from .entity import FlexitAuraEntity
from .model import FlexitAuraData


@dataclass(frozen=True, kw_only=True)
class FlexitAuraBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description carrying the accessor for the snapshot."""

    value_fn: Callable[[FlexitAuraData], bool | None]


BINARY_SENSORS: tuple[FlexitAuraBinarySensorDescription, ...] = (
    FlexitAuraBinarySensorDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: None if data.alarm is None else data.alarm != 0,
    ),
    FlexitAuraBinarySensorDescription(
        key="filter_warning",
        translation_key="filter_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: (
            None if data.filter_warning is None else data.filter_warning != 0
        ),
    ),
    FlexitAuraBinarySensorDescription(
        key="boost",
        translation_key="boost",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: None if data.boost is None else data.boost != 0,
    ),
    FlexitAuraBinarySensorDescription(
        key="humidity_control",
        translation_key="humidity_control",
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            None if data.humidity_control is None else data.humidity_control != 0
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitAuraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        FlexitAuraBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class FlexitAuraBinarySensor(FlexitAuraEntity, BinarySensorEntity):
    """One decoded flag exposed as a binary sensor."""

    entity_description: FlexitAuraBinarySensorDescription

    def __init__(
        self,
        coordinator: FlexitAuraCoordinator,
        description: FlexitAuraBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
