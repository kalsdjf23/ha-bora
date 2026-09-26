"""Load the integration and entity platforms inside real Home Assistant."""

from unittest.mock import patch

import pytest
from homeassistant import setup
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.ble import extractor
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def custom_components(enable_custom_integrations):
    pass


@pytest.fixture
async def loaded(hass):
    connection = Connection()
    original = setup.async_process_deps_reqs

    async def dependencies(hass, config, integration):
        # Only substitute the physical Bluetooth dependency. All BORA code,
        # coordinator and entity platforms run through the real HA lifecycle.
        if integration.domain == DOMAIN:
            return
        return await original(hass, config, integration)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="BORA X PURE",
        data={"address": ADDRESS},
        options={CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False},
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.setup.async_process_deps_reqs", side_effect=dependencies),
        patch("custom_components.bora.coordinator.create_connection", return_value=connection),
        patch(
            "homeassistant.components.bluetooth.async_register_callback", return_value=lambda: None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, connection
        if entry.state == ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_setup_read_only_entities_and_unload(hass, loaded):
    entry, connection = loaded
    assert entry.state == ConfigEntryState.LOADED
    states = hass.states.async_all()
    assert len(states) >= 15
    assert any(s.entity_id.startswith("sensor.") for s in states)
    assert all("/Get" in path for path, _ in connection.requests)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not connection.connected
    assert not connection.streams


async def test_coordinator_rejects_controls_when_disabled(hass, loaded):
    entry, connection = loaded
    before = len(connection.requests)
    with pytest.raises(HomeAssistantError, match="Enable"):
        await entry.runtime_data.async_execute(extractor.set_power_level(3))
    assert len(connection.requests) == before


async def test_confirmed_control_updates_real_ha_states(hass, loaded):
    entry, connection = loaded
    coordinator = entry.runtime_data
    coordinator.controls_enabled = True
    await coordinator.async_execute(extractor.set_power_level(3))
    await hass.async_block_till_done()
    assert coordinator.data["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 3
    assert sum(path.endswith("/SetExtractorMode") for path, _ in connection.requests) == 1
    await connection.disconnect()
    coordinator._on_disconnect()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    with pytest.raises(HomeAssistantError, match="unavailable"):
        await coordinator.async_execute(extractor.set_power_level(3))


async def test_simple_function_requires_both_control_options(hass, loaded):
    entry, connection = loaded
    coordinator = entry.runtime_data
    before = len(connection.requests)
    for controls, cooking in ((False, False), (False, True), (True, False)):
        coordinator.controls_enabled = controls
        coordinator.cooking_enabled = cooking
        with pytest.raises(HomeAssistantError, match="Enable"):
            await coordinator.async_set_simple_function("timer_disabled", False)
    assert len(connection.requests) == before


async def test_optional_diagnostics_work_in_monitoring_mode(hass, loaded):
    entry, connection = loaded
    before = len(connection.requests)
    await entry.runtime_data.async_collect_diagnostics()
    queries = connection.requests[before:]
    assert len(queries) == 6
    assert all("/Get" in path or "/List" in path for path, _ in queries)
    assert len(entry.runtime_data.device.diagnostic_snapshot) == 6
    # Missing optional responses are recorded as errors, never fake zero values.
    assert all(
        item["status"] == "error" for item in entry.runtime_data.device.diagnostic_snapshot.values()
    )


async def test_invalid_control_keeps_connection_available(hass, loaded):
    entry, connection = loaded
    coordinator = entry.runtime_data
    coordinator.controls_enabled = True
    before = len(connection.requests)
    with pytest.raises(HomeAssistantError, match="Unsupported extractor"):
        await coordinator.async_execute(extractor.set_power_level(100))
    assert len(connection.requests) == before
    assert coordinator.last_update_success
    assert connection.connected
