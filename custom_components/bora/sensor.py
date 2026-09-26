"""BORA readings; unverified egg-timer/filter units remain raw attributes."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime

from .ble import cooktop, favorites, presets, zone
from .entity import (
    BoraEntity,
    cooktop_settings,
    cooktop_status,
    enum_name,
    extractor_settings,
    extractor_status,
    levels,
    nested,
    pure_cooktop,
    pure_extractor,
    zone_name,
    zone_source,
    zone_uids,
)


class BoraSensor(BoraEntity, SensorEntity):
    def __init__(self, coordinator, key, name, source, value, *, attributes=None, diagnostic=False):
        super().__init__(coordinator, key, name, source)
        self._value = value
        self._attributes = attributes
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return None if self.snapshot is None else self._value(self.snapshot)

    @property
    def extra_state_attributes(self):
        if self.snapshot is None or self._attributes is None:
            return None
        return self._attributes(self.snapshot)


class BoraWifiStatusSensor(BoraSensor):
    """Show the last explicit diagnostic read, without polling or network IDs."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "wifi_status",
            "Last reported Wi-Fi status",
            lambda coord: getattr(coord.device, "wifi_snapshot", None),
            lambda snapshot: snapshot["connection_status_name"],
            attributes=lambda snapshot: {
                "connection_status": snapshot["connection_status"],
                "last_read": snapshot["read_at"],
            },
            diagnostic=True,
        )


def _program_attributes(coordinator, uid, status):
    preset = presets.reported_preset(
        coordinator.device.information, coordinator.device.descriptor, uid, status
    )
    return {
        "phase": zone.csf_phase_name(status),
        "catalogue_program": preset.name if preset else None,
        "parameters_raw": nested(status, "csf", "parameters"),
    }


def build_entities(coordinator):
    entities = [
        BoraWifiStatusSensor(coordinator),
        BoraSensor(
            coordinator,
            "extractor_level",
            "Extractor level",
            extractor_settings,
            lambda item: nested(item, "extractor_mode", "power_level"),
            attributes=lambda item: {
                "level_label": levels(coordinator, "extractor_descriptor").get(
                    nested(item, "extractor_mode", "power_level")
                ),
                "egg_timer_raw": item.get("egg_timer"),
                "configured_after_run_minutes": nested(item, "pure", "after_run_minutes"),
            },
        ),
        BoraSensor(
            coordinator,
            "extractor_mode",
            "Extractor mode",
            extractor_settings,
            lambda item: nested(item, "extractor_mode", "mode"),
        ),
        BoraSensor(
            coordinator,
            "child_lock",
            "Child lock state",
            cooktop_settings,
            lambda item: enum_name(item.get("childlock_setting"), cooktop.CHILD_LOCK_NAMES),
        ),
        BoraSensor(
            coordinator,
            "connectivity",
            "Connectivity setting",
            cooktop_settings,
            lambda item: enum_name(item.get("connectivity_setting"), cooktop.CONNECTIVITY_NAMES),
            diagnostic=True,
            attributes=lambda _: {
                "remaining_filter_lifetime_raw": nested(
                    pure_cooktop(coordinator), "remaining_filter_lifetime_raw"
                ),
                "dealer_menu_config": nested(pure_cooktop(coordinator), "dealer_menu_config"),
                "super_simple_mode": nested(pure_cooktop(coordinator), "super_simple_mode"),
            },
        ),
        BoraSensor(
            coordinator,
            "errors",
            "Reported error count",
            cooktop_status,
            lambda item: (
                len(item["current_primary_device_errors"])
                if item.get("current_primary_device_errors") is not None
                else None
            ),
            attributes=lambda item: {
                "codes": item.get("current_primary_device_errors"),
                "labels": [
                    enum_name(code, cooktop.ERROR_CODE_NAMES)
                    for code in (item.get("current_primary_device_errors") or [])
                ]
                if item.get("current_primary_device_errors") is not None
                else None,
            },
            diagnostic=True,
        ),
    ]
    remaining = BoraSensor(
        coordinator,
        "after_run_remaining",
        "After-run remaining",
        extractor_status,
        lambda item: (
            item["remaining_after_run_ms"] / 1000
            if item.get("remaining_after_run_ms") is not None
            else None
        ),
    )
    remaining._attr_native_unit_of_measurement = UnitOfTime.SECONDS
    remaining._attr_device_class = SensorDeviceClass.DURATION
    entities.append(remaining)
    if pure_extractor(coordinator) is not None:
        configured = BoraSensor(
            coordinator,
            "configured_after_run",
            "Configured after-run duration",
            pure_extractor,
            lambda item: item.get("after_run_minutes"),
        )
        configured._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        configured._attr_device_class = SensorDeviceClass.DURATION
        entities.append(configured)
    for uid in zone_uids(coordinator):
        prefix = zone_name(uid)
        source = zone_source(uid)
        def timer_source(coord, source=source):
            return nested(source(coord), "timer")

        for field in ("duration", "remaining"):
            timer = BoraSensor(
                coordinator,
                f"{uid}_timer_{field}",
                f"{prefix} timer {field}",
                timer_source,
                lambda item, field=field: (
                    item[field] / 1000 if item.get(field) is not None else None
                ),
                attributes=lambda item: {"timer_raw": item},
            )
            timer._attr_native_unit_of_measurement = UnitOfTime.SECONDS
            timer._attr_device_class = SensorDeviceClass.DURATION
            entities.append(timer)
        entities.extend(
            [
                BoraSensor(
                    coordinator,
                    f"{uid}_power",
                    f"{prefix} power level",
                    source,
                    lambda item: item.get("power_level"),
                    attributes=lambda item: {
                        "level_label": levels(coordinator, "zone_descriptor").get(
                            item.get("power_level")
                        ),
                        "timer_raw": item.get("timer"),
                        "bridged_to_uid": item.get("bridged_to_uid") or None,
                    },
                ),
                BoraSensor(
                    coordinator,
                    f"{uid}_mode",
                    f"{prefix} mode",
                    source,
                    lambda item: item.get("mode"),
                    attributes=lambda item: {
                        "heat_retention": enum_name(item.get("keep_warm"), zone.KEEP_WARM_MODES),
                        "heat_up_power": item.get("heat_up_power"),
                    },
                ),
                BoraSensor(
                    coordinator,
                    f"{uid}_csf",
                    f"{prefix} cooking program",
                    source,
                    lambda item: (
                        enum_name(nested(item, "csf", "parameters", "csf_type"), zone.CSF_TYPES)
                        if item.get("mode") == "csf" else None
                    ),
                    attributes=lambda item, uid=uid: _program_attributes(coordinator, uid, item),
                ),
                BoraSensor(
                    coordinator,
                    f"{uid}_csf_phase",
                    f"{prefix} cooking program phase",
                    source,
                    zone.csf_phase_name,
                ),
            ]
        )
        if presets.get_presets(coordinator.device.information, coordinator.device.descriptor, uid):
            target = BoraSensor(
                coordinator,
                f"{uid}_assist_target",
                f"{prefix} Assist target temperature",
                source,
                lambda item, uid=uid: presets.reported_target_celsius(
                    coordinator.device.information, coordinator.device.descriptor, uid, item
                ),
            )
            target._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            target._attr_device_class = SensorDeviceClass.TEMPERATURE
            entities.append(target)
    if favorites.supports_favorites(coordinator.device.information, coordinator.device.descriptor):
        for slot in (3, 4, 5):
            entities.append(
                BoraSensor(
                    coordinator,
                    f"saved_assist_{slot}",
                    f"Saved Assist {slot}",
                    lambda coord: coord.device.favorites_snapshot,
                    lambda snapshot, slot=slot: snapshot["slots"][slot]["label"],
                    attributes=lambda snapshot, slot=slot: {
                        "slot": slot,
                        "last_read": snapshot["read_at"],
                        "recognition": snapshot["slots"][slot]["state"],
                        "parameters_raw": snapshot["slots"][slot]["parameters"],
                        "ambiguous_parameters_raw": snapshot["slots"][slot]["candidates"],
                    },
                )
            )
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
