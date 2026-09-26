"""BORA setting controls, guarded separately for operations affecting cooking."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .ble import cooktop
from .entity import BoraEntity, cooktop_settings, nested, pure_cooktop


class BoraSwitch(BoraEntity, SwitchEntity):
    def __init__(
        self, coordinator, key, name, source, value, command, *, cooking=False, config=False
    ):
        super().__init__(coordinator, key, name, source, control=True, cooking=cooking)
        self._value, self._command = value, command
        if config:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return None if self.snapshot is None else self._value(self.snapshot)

    async def async_turn_on(self, **kwargs):
        await self._execute(self._command(True))

    async def async_turn_off(self, **kwargs):
        await self._execute(self._command(False))


def _disabled_functions(coordinator):
    return nested(pure_cooktop(coordinator), "super_simple_mode", "disabled_functions")


class BoraSimpleFunctionSwitch(BoraEntity, SwitchEntity):
    """Send one intent; the coordinator merges the complete group under its lock."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, field, name):
        super().__init__(
            coordinator,
            f"simple_{field}",
            name,
            _disabled_functions,
            control=True,
            cooking=True,
        )
        self._field = field

    @property
    def is_on(self):
        value = nested(self.snapshot, self._field)
        return None if value is None else not value

    async def _set_enabled(self, enabled):
        self._ensure_available()
        await self.coordinator.async_set_simple_function(self._field, enabled)

    async def async_turn_on(self, **kwargs):
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs):
        await self._set_enabled(False)


def build_entities(coordinator):
    entities = [
        BoraSwitch(
            coordinator,
            "set_paused",
            "Pause",
            cooktop_settings,
            lambda item: item.get("pause"),
            cooktop.set_paused,
            cooking=True,
        )
    ]
    if pure_cooktop(coordinator) is None:
        return entities
    for field, label, command, cooking in (
        ("clean_lock", "Cleaning lock", cooktop.set_cleaning_lock, True),
        ("permanent_child_lock", "Permanent child lock", cooktop.set_permanent_child_lock, True),
        (
            "automatic_pot_detection",
            "Automatic pan detection",
            cooktop.set_automatic_pot_detection,
            True,
        ),
    ):
        entities.append(
            BoraSwitch(
                coordinator,
                f"set_{field}",
                label,
                pure_cooktop,
                lambda item, field=field: item.get(field),
                command,
                cooking=cooking,
                config=True,
            )
        )
    if _disabled_functions(coordinator) is not None:
        for field, label in (
            ("cleaning_lock_disabled", "Cleaning lock in simple mode"),
            ("pause_disabled", "Pause in simple mode"),
            ("warming_disabled", "Warming in simple mode"),
            ("timer_disabled", "Timer in simple mode"),
            ("hot_key_disabled", "Hot key in simple mode"),
        ):
            entities.append(BoraSimpleFunctionSwitch(coordinator, field, label))
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
