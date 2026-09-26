"""BORA enumerated controls using advertised labels and known schema enums."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .ble import cooktop, extractor, presets, zone
from .entity import (
    BoraEntity,
    cooktop_settings,
    descriptor,
    levels,
    nested,
    option_labels,
    pure_cooktop,
    pure_extractor,
    zone_name,
    zone_source,
    zone_uids,
)


class BoraSelect(BoraEntity, SelectEntity):
    def __init__(
        self,
        coordinator,
        key,
        name,
        source,
        value,
        choices,
        command,
        *,
        cooking=False,
        requires=None,
        config=False,
    ):
        super().__init__(
            coordinator, key, name, source, control=True, cooking=cooking, requires=requires
        )
        self._value, self._choices, self._command = value, choices, command
        if config:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def options(self):
        return list(self._choices().values())

    @property
    def available(self):
        return super().available and bool(self.options)

    @property
    def current_option(self):
        return None if self.snapshot is None else self._choices().get(self._value(self.snapshot))

    async def async_select_option(self, option):
        choices = self._choices()
        value = next((index for index, label in choices.items() if label == option), None)
        if value is None:
            raise HomeAssistantError("BORA option is not advertised or supported")
        await self._execute(self._command(value))


class BoraAssistSelect(BoraEntity, SelectEntity):
    """Choose a local draft only; selecting never sends a cooking command."""

    def __init__(self, coordinator, uid):
        super().__init__(
            coordinator,
            f"{uid}_assist",
            f"{zone_name(uid)} Assist to start",
            zone_source(uid),
            control=True,
            cooking=True,
        )
        self._uid = uid

    def _choices(self):
        return option_labels(
            {
                item.preset_id: f"{item.name} ({item.target_celsius} °C)"
                for item in self.coordinator.assist_presets(self._uid)
            }
        )

    @property
    def options(self):
        return list(self._choices().values())

    @property
    def current_option(self):
        if self.snapshot is None:
            return None
        return self._choices().get(self.coordinator.assist_selections.get(self._uid))

    @property
    def available(self):
        return super().available and bool(self.options)

    async def async_select_option(self, option):
        self._ensure_available()
        selected = next((key for key, label in self._choices().items() if label == option), None)
        if selected is None:
            raise HomeAssistantError("BORA Assist is not advertised or supported")
        self.coordinator.select_assist(self._uid, selected)


def _volume_levels(coordinator):
    values = nested(coordinator.device.descriptor, "signal_volume_levels") or []
    return option_labels({item["index"]: item["level_name"] for item in values})


def _after_run_options(coordinator):
    values = (
        nested(descriptor(coordinator, "extractor_descriptor"), "pure", "after_run_durations") or []
    )
    return {
        value: f"{extractor.AFTER_RUN_MINUTES[value]} min"
        for value in values
        if value in extractor.AFTER_RUN_MINUTES
    }


def build_entities(coordinator):
    entities = [
        BoraSelect(
            coordinator,
            "set_child_lock",
            "Child lock",
            cooktop_settings,
            lambda item: item.get("childlock_setting"),
            lambda: {key: value for key, value in cooktop.CHILD_LOCK_NAMES.items() if key},
            cooktop.set_child_lock,
            cooking=True,
            config=True,
        )
    ]
    if _volume_levels(coordinator):
        entities.append(
            BoraSelect(
                coordinator,
                "signal_volume",
                "Signal volume",
                cooktop_settings,
                lambda item: item.get("signal_volume"),
                lambda: _volume_levels(coordinator),
                lambda value: cooktop.set_signal_volume(
                    value, allowed_levels=_volume_levels(coordinator)
                ),
                config=True,
            )
        )
    if pure_extractor(coordinator) is not None and _after_run_options(coordinator):
        entities.append(
            BoraSelect(
                coordinator,
                "after_run_duration",
                "After-run duration",
                pure_extractor,
                lambda item: item.get("after_run_duration"),
                lambda: _after_run_options(coordinator),
                lambda value: extractor.set_after_run_duration(
                    value, allowed_values=_after_run_options(coordinator)
                ),
                config=True,
            )
        )
    if pure_cooktop(coordinator) is not None:
        for key, label, field, names, command, cooking in (
            (
                "sensitivity",
                "Touch sensitivity",
                "sensitivity",
                cooktop.SENSITIVITY_NAMES,
                cooktop.set_touch_sensitivity,
                False,
            ),
            (
                "max_operation",
                "Maximum operation duration",
                "max_op_duration",
                cooktop.MAX_OP_DURATION_NAMES,
                cooktop.set_maximum_op_duration,
                True,
            ),
        ):
            entities.append(
                BoraSelect(
                    coordinator,
                    key,
                    label,
                    pure_cooktop,
                    lambda item, field=field: item.get(field),
                    lambda names=names: {key: value for key, value in names.items() if key},
                    command,
                    cooking=cooking,
                    config=True,
                )
            )
    mode_types = descriptor(coordinator, "zone_descriptor").get("zone_mode_types", [])
    power = sorted(levels(coordinator, "zone_descriptor"))
    for uid in zone_uids(coordinator):
        name, source = zone_name(uid), zone_source(uid)
        if presets.get_presets(coordinator.device.information, coordinator.device.descriptor, uid):
            entities.append(BoraAssistSelect(coordinator, uid))
        if 1 in mode_types and power and len(power) != power[-1] - power[0] + 1:
            entities.append(
                BoraSelect(
                    coordinator,
                    f"{uid}_set_power",
                    f"{name} power",
                    source,
                    lambda item: item.get("power_level"),
                    lambda: option_labels(levels(coordinator, "zone_descriptor")),
                    lambda value, uid=uid: zone.set_power(
                        uid, value, allowed_levels=levels(coordinator, "zone_descriptor")
                    ),
                    cooking=True,
                    requires=lambda coord: (
                        1 in descriptor(coord, "zone_descriptor").get("zone_mode_types", [])
                    ),
                )
            )
        if pure_cooktop(coordinator) is None:
            continue
        if 3 in mode_types and descriptor(coordinator, "zone_descriptor").get(
            "variable_heat_retention_support"
        ):
            entities.append(
                BoraSelect(
                    coordinator,
                    f"{uid}_keep_warm",
                    f"{name} heat retention",
                    source,
                    lambda item: item.get("keep_warm"),
                    lambda: {key: value for key, value in zone.KEEP_WARM_MODES.items() if key},
                    lambda value, uid=uid: zone.set_keep_warm(uid, value),
                    cooking=True,
                    requires=lambda coord: (
                        pure_cooktop(coord) is not None
                        and 3 in descriptor(coord, "zone_descriptor").get("zone_mode_types", [])
                        and bool(
                            descriptor(coord, "zone_descriptor").get(
                                "variable_heat_retention_support"
                            )
                        )
                    ),
                )
            )
        heat_levels = {
            index: label
            for index, label in levels(coordinator, "zone_descriptor").items()
            if index > 0 and label.isdecimal()
        }
        if 4 in mode_types and heat_levels:
            entities.append(
                BoraSelect(
                    coordinator,
                    f"{uid}_heat_up",
                    f"{name} automatic heat-up",
                    source,
                    lambda item: item.get("heat_up_power"),
                    lambda: option_labels(
                        {
                            index: label
                            for index, label in levels(coordinator, "zone_descriptor").items()
                            if index > 0 and label.isdecimal()
                        }
                    ),
                    lambda value, uid=uid: zone.set_heat_up(
                        uid, value, allowed_levels=levels(coordinator, "zone_descriptor")
                    ),
                    cooking=True,
                    requires=lambda coord: (
                        pure_cooktop(coord) is not None
                        and 4 in descriptor(coord, "zone_descriptor").get("zone_mode_types", [])
                    ),
                )
            )
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
