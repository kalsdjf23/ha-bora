"""Boolean BORA observations without inferring heating or pan presence."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .ble import cooktop, zone
from .entity import (
    BoraEntity,
    cooktop_settings,
    cooktop_status,
    extractor_status,
    nested,
    pure_cooktop,
    zone_name,
    zone_source,
    zone_uids,
)


class BoraBinarySensor(BoraEntity, BinarySensorEntity):
    def __init__(
        self, coordinator, key, name, source, value, *, diagnostic=False, device_class=None
    ):
        super().__init__(coordinator, key, name, source)
        self._value = value
        self._attr_device_class = device_class
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return None if self.snapshot is None else self._value(self.snapshot)


def build_entities(coordinator):
    entities = [
        BoraBinarySensor(
            coordinator, "paused", "Paused", cooktop_settings, lambda item: item.get("pause")
        ),
        BoraBinarySensor(
            coordinator,
            "after_run",
            "After-run active",
            extractor_status,
            lambda item: (
                item["remaining_after_run_ms"] > 0
                if item.get("remaining_after_run_ms") is not None
                else None
            ),
        ),
        BoraBinarySensor(
            coordinator,
            "ready_for_sleep",
            "Ready for sleep",
            cooktop_status,
            lambda item: item.get("ready_for_sleep"),
            diagnostic=True,
        ),
        BoraBinarySensor(
            coordinator,
            "recovery",
            "Recovery active",
            cooktop_status,
            lambda item: item.get("recovery_state_active"),
            diagnostic=True,
        ),
    ]
    if pure_cooktop(coordinator) is not None:
        entities.extend(
            [
                BoraBinarySensor(
                    coordinator,
                    "cleaning_lock",
                    "Cleaning lock active",
                    pure_cooktop,
                    lambda item: item.get("clean_lock"),
                ),
                BoraBinarySensor(
                    coordinator,
                    "simple_mode",
                    "Simple mode active",
                    pure_cooktop,
                    lambda item: nested(item, "super_simple_mode", "active"),
                    diagnostic=True,
                ),
                BoraBinarySensor(
                    coordinator,
                    "filter_change_required",
                    "Filter replacement required",
                    pure_cooktop,
                    cooktop.filter_change_required,
                    device_class=BinarySensorDeviceClass.PROBLEM,
                ),
            ]
        )
    for uid in zone_uids(coordinator):
        name = zone_name(uid)
        source = zone_source(uid)
        entities.extend(
            [
                BoraBinarySensor(
                    coordinator,
                    f"{uid}_residual_heat",
                    f"{name} residual heat",
                    source,
                    lambda item: item.get("residual_heat"),
                    device_class=BinarySensorDeviceClass.HEAT,
                ),
                BoraBinarySensor(
                    coordinator,
                    f"{uid}_pot_detection",
                    f"{name} pan detection active",
                    source,
                    lambda item: item.get("pot_detection_active"),
                    diagnostic=True,
                ),
                BoraBinarySensor(
                    coordinator,
                    f"{uid}_bridged",
                    f"{name} bridged",
                    source,
                    lambda item: item.get("bridged"),
                ),
                BoraBinarySensor(
                    coordinator,
                    f"{uid}_timer_running",
                    f"{name} timer running",
                    lambda coord, source=source: nested(source(coord), "timer"),
                    lambda item: item.get("running"),
                ),
                BoraBinarySensor(
                    coordinator,
                    f"{uid}_assist_confirmation_required",
                    f"{name} Assist confirmation required",
                    source,
                    zone.csf_confirmation_required,
                ),
            ]
        )
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
