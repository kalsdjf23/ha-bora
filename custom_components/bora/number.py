"""Descriptor-limited manual zone power controls."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import HomeAssistantError

from .ble import zone
from .entity import BoraEntity, descriptor, levels, zone_name, zone_source, zone_uids


class BoraZonePower(BoraEntity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:stove"

    def __init__(self, coordinator, uid):
        super().__init__(
            coordinator,
            f"{uid}_set_power",
            f"{zone_name(uid)} power",
            zone_source(uid),
            control=True,
            cooking=True,
            requires=lambda coord: (
                1 in descriptor(coord, "zone_descriptor").get("zone_mode_types", [])
                and bool(levels(coord, "zone_descriptor"))
            ),
        )
        self._uid = uid
        self._initial_levels = levels(coordinator, "zone_descriptor")

    @property
    def native_min_value(self):
        return min(levels(self.coordinator, "zone_descriptor") or self._initial_levels)

    @property
    def native_max_value(self):
        return max(levels(self.coordinator, "zone_descriptor") or self._initial_levels)

    @property
    def native_value(self):
        return None if self.snapshot is None else self.snapshot.get("power_level")

    @property
    def extra_state_attributes(self):
        return {"level_labels": levels(self.coordinator, "zone_descriptor")}

    async def async_set_native_value(self, value):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not value.is_integer())
        ):
            raise HomeAssistantError("Power level must be an advertised integer")
        await self._execute(
            zone.set_power(
                self._uid, int(value), allowed_levels=levels(self.coordinator, "zone_descriptor")
            )
        )


def build_entities(coordinator):
    available = sorted(levels(coordinator, "zone_descriptor"))
    if not available or len(available) != available[-1] - available[0] + 1:
        return []
    if 1 not in descriptor(coordinator, "zone_descriptor").get("zone_mode_types", []):
        return []
    return [BoraZonePower(coordinator, uid) for uid in zone_uids(coordinator)]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
