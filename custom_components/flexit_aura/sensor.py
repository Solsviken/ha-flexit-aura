"""Read-only sensors for the Flexit Aura."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AIR_MODES, TIMER_MODES
from .coordinator import FlexitAuraConfigEntry, FlexitAuraCoordinator
from .entity import FlexitAuraEntity
from .model import FlexitAuraData


@dataclass(frozen=True, kw_only=True)
class FlexitAuraSensorDescription(SensorEntityDescription):
    """Sensor description carrying the accessor for the decoded snapshot."""

    value_fn: Callable[[FlexitAuraData], float | str | None]


SENSORS: tuple[FlexitAuraSensorDescription, ...] = (
    FlexitAuraSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
    FlexitAuraSensorDescription(
        key="fan1_rpm",
        translation_key="fan1_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.fan1_rpm,
    ),
    FlexitAuraSensorDescription(
        key="fan2_rpm",
        translation_key="fan2_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # The Aura 160 has one reversing fan, so this register reads 0 there.
        # Left available for the two-fan units in the same family.
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.fan2_rpm,
    ),
    FlexitAuraSensorDescription(
        key="filter_remaining",
        translation_key="filter_remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.filter_remaining_days,
    ),
    FlexitAuraSensorDescription(
        key="filter_interval",
        translation_key="filter_interval",
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.filter_interval_days,
    ),
    FlexitAuraSensorDescription(
        key="runtime",
        translation_key="runtime",
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.runtime_hours,
    ),
    FlexitAuraSensorDescription(
        key="humidity_limit",
        translation_key="humidity_limit",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.humidity_limit,
    ),
    FlexitAuraSensorDescription(
        key="air_mode",
        translation_key="air_mode_sensor",
        device_class=SensorDeviceClass.ENUM,
        options=list(AIR_MODES.values()),
        entity_registry_enabled_default=False,
        value_fn=lambda data: AIR_MODES.get(data.air_mode),
    ),
    FlexitAuraSensorDescription(
        key="timer_mode",
        translation_key="timer_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(TIMER_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: TIMER_MODES.get(data.timer_mode),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitAuraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        FlexitAuraSensor(coordinator, description) for description in SENSORS
    )


class FlexitAuraSensor(FlexitAuraEntity, SensorEntity):
    """One decoded register exposed as a sensor."""

    entity_description: FlexitAuraSensorDescription

    def __init__(
        self,
        coordinator: FlexitAuraCoordinator,
        description: FlexitAuraSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)
