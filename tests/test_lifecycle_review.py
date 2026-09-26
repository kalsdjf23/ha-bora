"""Independent offline regressions for setup and shutdown resource cleanup."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import setup
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.const import CONF_ENABLE_CONTROLS, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def custom_components(enable_custom_integrations):
    pass


async def test_review_late_setup_registration_failure_closes_connection(hass):
    """Bluetooth callback registration can fail after all initial reads succeed."""
    connection = Connection()
    original_dependencies = setup.async_process_deps_reqs

    async def dependencies(hass, config, integration):
        if integration.domain == DOMAIN:
            return
        return await original_dependencies(hass, config, integration)

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="BORA X PURE",
        data={"address": ADDRESS}, options={CONF_ENABLE_CONTROLS: True},
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.setup.async_process_deps_reqs", side_effect=dependencies),
        patch("custom_components.bora.coordinator.create_connection", return_value=connection),
        patch(
            "homeassistant.components.bluetooth.async_register_callback",
            side_effect=RuntimeError("Simulated callback registration failure"),
        ),
    ):
        try:
            assert not await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.SETUP_ERROR
            # A failed entry must not leave a live control entity connected.
            fan = next((state.entity_id for state in hass.states.async_all()
                        if state.entity_id.startswith("fan.")), None)
            if fan:
                try:
                    await hass.services.async_call(
                        "fan", "turn_on", {"entity_id": fan, "percentage": 50}, blocking=True
                    )
                except HomeAssistantError:
                    pass
            assert not any("/Set" in path for path, _body in connection.requests)
            assert not connection.connected
            assert not connection.streams
        finally:
            # Explicit cleanup makes the regression safe to run while it fails.
            if hasattr(entry, "runtime_data"):
                await entry.runtime_data.async_close()
            await hass.config_entries.async_unload_platforms(
                entry,
                ["sensor", "binary_sensor", "fan", "select", "number", "switch", "button"],
            )
            await hass.async_block_till_done()


async def test_review_cancelled_close_still_shuts_down_ha_refresh(hass):
    """Cancellation during device cleanup must not leave HA timers/debouncer live."""
    connection = Connection()
    entry = MockConfigEntry(domain=DOMAIN, data={"address": ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    try:
        coordinator.device.shutdown = AsyncMock(side_effect=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            await coordinator.async_close()
        assert coordinator._closed
        assert coordinator._shutdown_requested
    finally:
        await coordinator.async_shutdown()
        await connection.disconnect()
