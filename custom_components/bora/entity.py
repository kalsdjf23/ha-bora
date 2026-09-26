"""Shared entity plumbing and capability lookup for BORA Local."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

type Snapshot = dict[str, Any]
type Source = Callable[[Any], Snapshot | None]


def nested(value: Any, *keys: str) -> Any:
    """Missing snapshots are unknown, never synthesized defaults."""
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def extractor_status(coordinator) -> Snapshot | None:
    return nested(coordinator.data, "extractor")


def extractor_settings(coordinator) -> Snapshot | None:
    return nested(coordinator.data, "extractor", "extractor_settings")


def cooktop_status(coordinator) -> Snapshot | None:
    return nested(coordinator.data, "cooktop")


def cooktop_settings(coordinator) -> Snapshot | None:
    return nested(coordinator.data, "cooktop", "cooktop_settings")


def pure_cooktop(coordinator) -> Snapshot | None:
    return nested(cooktop_settings(coordinator), "pure")


def pure_extractor(coordinator) -> Snapshot | None:
    return nested(extractor_settings(coordinator), "pure")


def zone_source(uid: str) -> Source:
    def source(coordinator):
        status = nested(coordinator.data, "zones", uid)
        if status is not None and status.get("settings_present") is not False:
            return status
        return None

    return source


def descriptor(coordinator, key: str) -> Snapshot:
    return nested(coordinator.device.descriptor, key) or {}


def zone_uids(coordinator) -> list[str]:
    values = nested(coordinator.device.descriptor, "zone_uids") or {}
    return list(dict.fromkeys(uid for uid in values.values() if isinstance(uid, str) and uid))


def zone_name(uid: str) -> str:
    return uid.replace("_", " ").replace("-", " ").capitalize()


def levels(coordinator, key: str) -> dict[int, str]:
    values = descriptor(coordinator, key).get("power_levels", [])
    return {
        item["index"]: item["level_name"]
        for item in values
        if isinstance(item.get("index"), int) and isinstance(item.get("level_name"), str)
    }


def option_labels(values: dict[int, str]) -> dict[int, str]:
    """Keep labels from the device while making duplicate/empty labels selectable."""
    return {
        index: label if label and list(values.values()).count(label) == 1 else f"{label} ({index})"
        for index, label in values.items()
    }


def enum_name(value: int | None, names: dict[int, str]) -> str | None:
    return None if value is None else names.get(value, f"unknown_{value}")


class BoraEntity(CoordinatorEntity):
    """One appliance, stable Bluetooth identity and a second control guard."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        key: str,
        name: str,
        source: Source,
        *,
        control: bool = False,
        cooking: bool = False,
        requires: Callable[[Any], bool] | None = None,
    ) -> None:
        super().__init__(coordinator)
        identity = getattr(coordinator.entry, "unique_id", None) or coordinator.entry.entry_id
        self._attr_unique_id = f"{identity}_{key}"
        self._attr_name = name
        self._source = source
        self._control = control
        self._cooking = cooking
        self._requires = requires
        info = coordinator.device.information or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            manufacturer="BORA",
            name=coordinator.entry.title,
            model=(info.get("product_name") or "Cooktop").replace("_", " "),
            hw_version=info.get("cm_hw_version_no") or None,
            sw_version=info.get("cm_sw_version_no") or None,
        )

    @property
    def snapshot(self) -> Snapshot | None:
        return self._source(self.coordinator)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.snapshot is not None
            and (not self._control or self.coordinator.controls_enabled)
            and (not self._cooking or self.coordinator.cooking_enabled)
            and (self._requires is None or self._requires(self.coordinator))
        )

    def _ensure_available(self) -> None:
        if not self.available:
            raise HomeAssistantError("BORA entity is unavailable or disabled")

    async def _execute(self, command: tuple[str, bytes]) -> None:
        self._ensure_available()
        await self.coordinator.async_execute(command, cooking=self._cooking)
