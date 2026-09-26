"""Explicit supported actions; no resets, dealer writes or undocumented toggles."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .ble import extractor, favorites, presets, zone
from .entity import (
    BoraEntity,
    cooktop_status,
    descriptor,
    extractor_status,
    nested,
    pure_cooktop,
    zone_name,
    zone_source,
    zone_uids,
)


class BoraButton(BoraEntity, ButtonEntity):
    def __init__(self, coordinator, key, name, source, command, *, cooking=False, requires=None):
        super().__init__(
            coordinator, key, name, source, control=True, cooking=cooking, requires=requires
        )
        self._command = command

    async def async_press(self):
        await self._execute(self._command())


class BoraDiagnosticsButton(BoraEntity, ButtonEntity):
    """Explicitly collect optional read-only diagnostics, even with controls off."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator):
        super().__init__(
            coordinator, "refresh_diagnostics", "Refresh diagnostics", lambda coord: coord.data
        )

    async def async_press(self):
        self._ensure_available()
        await self.coordinator.async_collect_diagnostics()


class BoraStartAssistButton(BoraEntity, ButtonEntity):
    """Start only a valid local choice on a known idle, unbridged zone."""

    def __init__(self, coordinator, uid):
        self._uid = uid
        super().__init__(
            coordinator,
            f"{uid}_start_assist",
            f"{zone_name(uid)} start Assist",
            zone_source(uid),
            control=True,
            cooking=True,
            requires=self._can_start,
        )

    def _can_start(self, coordinator):
        status = zone_source(self._uid)(coordinator)
        selected = coordinator.assist_selections.get(self._uid)
        return (
            pure_cooktop(coordinator) is not None
            and nested(status, "settings_present") is True
            and nested(status, "mode") == "power_level"
            and nested(status, "power_level") == 0
            and nested(status, "bridged") is False
            and not nested(status, "bridged_to_uid")
            and any(item.preset_id == selected for item in coordinator.assist_presets(self._uid))
            and not coordinator.device.assist_start_blocked(self._uid)
        )

    async def async_press(self):
        self._ensure_available()
        await self.coordinator.async_start_assist(self._uid)


class BoraRefreshFavoritesButton(BoraEntity, ButtonEntity):
    """Read the favorite bank only when explicitly requested, even in monitoring mode."""

    def __init__(self, coordinator):
        super().__init__(
            coordinator, "refresh_saved_assists", "Refresh saved Assists", cooktop_status,
            requires=lambda coord: favorites.supports_favorites(
                coord.device.information, coord.device.descriptor
            ),
        )

    async def async_press(self):
        self._ensure_available()
        await self.coordinator.async_refresh_favorites()


def build_entities(coordinator):
    entities = [BoraDiagnosticsButton(coordinator)]
    if favorites.supports_favorites(coordinator.device.information, coordinator.device.descriptor):
        entities.append(BoraRefreshFavoritesButton(coordinator))
    if descriptor(coordinator, "extractor_descriptor"):
        entities.append(
            BoraButton(
                coordinator,
                "stop_after_run",
                "Stop after-run",
                extractor_status,
                extractor.stop_after_run,
                requires=lambda coord: (
                    (nested(extractor_status(coord), "remaining_after_run_ms") or 0) > 0
                ),
            )
        )
    supported = descriptor(coordinator, "zone_descriptor").get("zone_mode_types", [])
    if 2 in supported:
        for uid in zone_uids(coordinator):
            if presets.get_presets(
                coordinator.device.information, coordinator.device.descriptor, uid
            ):
                entities.append(BoraStartAssistButton(coordinator, uid))
            entities.append(
                BoraButton(
                    coordinator,
                    f"{uid}_stop_csf",
                    f"{zone_name(uid)} stop cooking program",
                    zone_source(uid),
                    lambda uid=uid: zone.stop_csf(uid),
                    cooking=True,
                    requires=lambda coord, uid=uid: (
                        nested(zone_source(uid)(coord), "mode") == "csf"
                    ),
                )
            )
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
