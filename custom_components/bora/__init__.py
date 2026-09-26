"""BORA Local Bluetooth integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import BoraCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry[BoraCoordinator]) -> bool:
    from homeassistant.components import bluetooth
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
    from homeassistant.core import callback

    from .const import PLATFORMS
    from .coordinator import BoraCoordinator

    coordinator = BoraCoordinator(hass, entry)

    @callback
    def on_advertisement(_info, _change):
        if not coordinator.last_update_success:
            entry.async_create_background_task(
                hass, coordinator.async_request_refresh(), "BORA reconnect after advertisement"
            )

    async def on_stop(_event):
        await coordinator.async_close()

    platforms_started = False
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        entry.async_on_unload(
            bluetooth.async_register_callback(
                hass,
                on_advertisement,
                {"address": entry.data["address"], "connectable": True},
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop))
        platforms_started = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        try:
            if platforms_started:
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        finally:
            await coordinator.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry[BoraCoordinator]) -> bool:
    from .const import PLATFORMS

    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_close()
        return True
    return False
