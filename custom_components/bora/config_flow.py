"""Discovery, explicit pairing and options for BORA Local."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from bleak.exc import BleakError
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .adapter import create_connection
from .ble.transport import SERVICE_UUID, BoraError, PairingRequired
from .ble.wire import ProtocolError
from .const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN, NAME


def is_bora(info) -> bool:
    return info.name == "X PURE" or SERVICE_UUID in {u.lower() for u in info.service_uuids}


async def async_probe(hass, address: str) -> dict:
    """Pair only after confirmation, validate descriptors, and always disconnect."""
    from .ble.client import BoraDevice

    connection = create_connection(hass, address)
    device = BoraDevice(connection)
    try:
        async with asyncio.timeout(60):
            await device.initialize(pair=True, subscribe=False)
            return device.information
    finally:
        await connection.disconnect()


class BoraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name = NAME

    async def async_step_bluetooth(self, discovery_info):
        """Discovery only offers a flow; it never pairs automatically."""
        if not is_bora(discovery_info):
            return self.async_abort(reason="unsupported_device")
        self._address = discovery_info.address.upper()
        self._name = discovery_info.name or NAME
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_pair()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not address:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._address = address
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return await self.async_step_pair()
        devices = {
            info.address.upper(): f"{info.name} ({info.address})"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
            if is_bora(info) and info.address.upper() not in self._async_current_ids()
        }
        schema = vol.Schema({vol.Required(CONF_ADDRESS): vol.In(devices) if devices else str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_pair(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await async_probe(self.hass, self._address)
            except PairingRequired:
                errors["base"] = "pairing_failed"
            except BoraError, BleakError, TimeoutError, ProtocolError:
                errors["base"] = "cannot_connect"
            else:
                if self.source == config_entries.SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(self._get_reauth_entry())
                product_name = (info.get("product_name") or self._name).replace("_", " ").upper()
                return self.async_create_entry(
                    title=f"BORA {product_name}"
                    if not product_name.startswith("BORA")
                    else product_name,
                    data={CONF_ADDRESS: self._address},
                    options={CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False},
                )
        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"name": self._name},
        )

    async def async_step_reauth(self, entry_data):
        entry = self._get_reauth_entry()
        self._address = entry_data[CONF_ADDRESS].strip().upper()
        self._name = entry.title
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_mismatch()
        return await self.async_step_pair()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BoraOptionsFlow()


class BoraOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if not user_input[CONF_ENABLE_CONTROLS]:
                user_input[CONF_ENABLE_COOKING] = False
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_CONTROLS, default=options.get(CONF_ENABLE_CONTROLS, False)
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_COOKING, default=options.get(CONF_ENABLE_COOKING, False)
                    ): bool,
                }
            ),
        )
