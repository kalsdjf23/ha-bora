"""Push updates plus periodic status reconciliation and reconnect for BORA."""

from __future__ import annotations

import logging
from datetime import timedelta

from bleak.exc import BleakError
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adapter import create_connection
from .ble import cooktop, presets, zone
from .ble.client import BoraDevice, CommandNotConfirmed, UnsupportedValue
from .ble.transport import BoraError, PairingRequired
from .ble.wire import Message, ProtocolError
from .const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BoraCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry):
        super().__init__(
            hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(seconds=30)
        )
        self.entry = entry
        self.controls_enabled = entry.options.get(CONF_ENABLE_CONTROLS, False)
        self.cooking_enabled = self.controls_enabled and entry.options.get(
            CONF_ENABLE_COOKING, False
        )
        self._closed = False
        # Local UI choices only. No implicit/default choice and no transmission
        # on selection, reconnect, startup or entity restoration.
        self.assist_selections: dict[str, int] = {}
        connection = create_connection(
            hass, entry.data["address"], disconnected=self._on_disconnect
        )
        self.device = BoraDevice(
            connection, updated=self._on_update,
            favorites_updated=self._on_optional_update,
            diagnostics_updated=self._on_optional_update,
        )

    def _on_optional_update(self) -> None:
        if not self._closed:
            self.async_update_listeners()

    def _on_update(self) -> None:
        if not self._closed:
            self.async_set_updated_data(self.device.snapshot)

    def _on_disconnect(self) -> None:
        self.device.invalidate_favorites()
        self.device.invalidate_wifi()
        if not self._closed:
            self.async_set_update_error(UpdateFailed("BORA Bluetooth connection lost"))

    async def _async_update_data(self) -> dict:
        if self._closed:
            raise UpdateFailed("BORA integration has been unloaded")
        try:
            return await self.device.refresh()
        except PairingRequired as err:
            raise ConfigEntryAuthFailed("Pair this Bluetooth adapter with BORA again") from err
        except (BoraError, BleakError, ProtocolError, TimeoutError) as err:
            await self.device.close()
            raise UpdateFailed("BORA is not reachable or did not return valid status") from err

    async def async_execute(self, command: tuple[str, bytes], *, cooking: bool = False) -> None:
        # Enforce the same cooking boundary even if a caller omits its flag.
        path, body = command
        cooking = cooking or path.startswith(zone.SERVICE_PATH) or path in {
            cooktop.PREFIX + "SetPaused",
            cooktop.PREFIX + "SetChildLock",
        }
        if path == cooktop.PREFIX + "SetSpecificCooktopSetting":
            try:
                field = Message(body).message(1).oneof(set(range(1, 9)))
            except ProtocolError as err:
                raise HomeAssistantError("Invalid BORA control request") from err
            # Cleaning/child locks, pan detection, operation duration and the
            # complete simple-mode group can affect cooking. Sensitivity cannot.
            cooking = cooking or field in {1, 2, 5, 6, 7}
        await self._async_control(lambda: self.device.execute(command), cooking=cooking)

    async def async_set_simple_function(self, field: str, enabled: bool) -> None:
        await self._async_control(
            lambda: self.device.set_simple_function(field, enabled), cooking=True
        )

    def assist_presets(self, uid: str) -> tuple[presets.Preset, ...]:
        return presets.get_presets(self.device.information, self.device.descriptor, uid)

    def select_assist(self, uid: str, preset_id: int) -> None:
        """Choose a local draft; this method performs no Bluetooth operation."""
        self._ensure_available()
        if not self.controls_enabled or not self.cooking_enabled:
            raise HomeAssistantError("Enable BORA cooking controls before choosing an Assist")
        if isinstance(preset_id, bool) or not isinstance(preset_id, int) or preset_id not in {
            item.preset_id for item in self.assist_presets(uid)
        }:
            raise HomeAssistantError("This Assist is not supported by the selected zone")
        self.assist_selections[uid] = preset_id
        self.async_update_listeners()

    async def async_start_assist(self, uid: str) -> None:
        preset_id = self.assist_selections.get(uid)
        if preset_id is None:
            raise HomeAssistantError("Choose an Assist for this zone before pressing Start")
        await self._async_control(
            lambda: self.device.start_assist(uid, preset_id), cooking=True
        )

    def _ensure_available(self) -> None:
        if self._closed or not self.last_update_success:
            raise HomeAssistantError("BORA is unavailable; the command was not queued")

    async def _async_control(self, operation, *, cooking: bool) -> None:
        if not self.controls_enabled or (cooking and not self.cooking_enabled):
            raise HomeAssistantError(
                "Enable the corresponding BORA controls in integration options"
            )
        self._ensure_available()
        try:
            data = await operation()
        except UnsupportedValue as err:
            raise HomeAssistantError(str(err)) from err
        except CommandNotConfirmed as err:
            # A valid readback can differ while the appliance is still applying
            # the request. Show it without declaring the device unreachable or
            # reissuing the operation.
            self.async_set_updated_data(self.device.snapshot)
            raise HomeAssistantError(
                "BORA does not yet show the requested state. "
                "Check the appliance before trying again."
            ) from err
        except (BoraError, BleakError, ProtocolError, TimeoutError) as err:
            # A timeout after transmission has an uncertain outcome. Do not
            # retry the operation or claim that the requested setting was applied.
            self.async_set_update_error(UpdateFailed("BORA command could not be confirmed"))
            raise HomeAssistantError(
                "BORA could not confirm this operation. Check the appliance before trying again."
            ) from err
        self.async_set_updated_data(data)

    async def async_collect_diagnostics(self) -> None:
        """Explicit read-only refresh, also available in monitoring mode."""
        self._ensure_available()
        try:
            await self.device.collect_diagnostics()
        except (BoraError, BleakError, ProtocolError, TimeoutError) as err:
            raise HomeAssistantError("BORA diagnostics could not be collected") from err
        finally:
            self._finish_optional_read()

    def _finish_optional_read(self) -> None:
        if self._closed:
            return
        if self.device.connection.connected:
            # Only optional cache changed. Do not turn a failed main status
            # update into success merely because an auxiliary read finished.
            self.async_update_listeners()
        else:
            self._on_disconnect()

    async def async_refresh_favorites(self) -> None:
        self._ensure_available()
        try:
            await self.device.refresh_favorites()
        except (BoraError, BleakError, ProtocolError, TimeoutError) as err:
            raise HomeAssistantError("Saved BORA Assists could not be read") from err
        finally:
            self._finish_optional_read()

    async def async_close(self) -> None:
        self._closed = True
        try:
            await self.device.shutdown()
        finally:
            await self.async_shutdown()
