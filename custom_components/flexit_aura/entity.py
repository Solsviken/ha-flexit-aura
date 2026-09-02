"""Shared entity base for the Flexit Aura integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN, MANUFACTURER, MODEL
from .coordinator import FlexitAuraCoordinator


class FlexitAuraEntity(CoordinatorEntity[FlexitAuraCoordinator]):
    """Base entity tying every platform to the same device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlexitAuraCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            serial_number=device_id,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
