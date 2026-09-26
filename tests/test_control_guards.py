"""Central cooking permissions hold even when callers omit the cooking flag."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.ble import cooktop, extractor, zone
from custom_components.bora.ble.wire import uint
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator

COOKING_COMMANDS = [
    pytest.param(cooktop.set_paused(False), id="resume"),
    pytest.param(cooktop.set_child_lock(3), id="unlock"),
    pytest.param(cooktop.set_cleaning_lock(False), id="cleaning-lock"),
    pytest.param(cooktop.set_permanent_child_lock(False), id="permanent-child-lock"),
    pytest.param(cooktop.set_automatic_pot_detection(True), id="pan-detection"),
    pytest.param(cooktop.set_maximum_op_duration(3), id="operation-duration"),
    pytest.param(
        cooktop.set_super_simple_disabled_functions(
            cleaning_lock_disabled=False,
            pause_disabled=False,
            warming_disabled=False,
            timer_disabled=False,
            hot_key_disabled=False,
        ),
        id="simple-functions",
    ),
    pytest.param(zone.set_power("front_left", 3), id="zone-power"),
    pytest.param(zone.set_keep_warm("front_left", 2), id="warming"),
    pytest.param(zone.set_heat_up("front_left", 3), id="heat-up"),
    pytest.param(zone.set_timer("front_left", 1000), id="zone-timer"),
    pytest.param(zone.set_timer_state("front_left", True), id="zone-timer-state"),
    pytest.param(zone.stop_csf("front_left"), id="stop-program"),
]

GENERAL_COMMANDS = [
    pytest.param(extractor.set_power_level(3), id="extractor-power"),
    pytest.param(extractor.set_auto_mode(), id="automatic-extraction"),
    pytest.param(extractor.set_after_run_duration(2), id="after-run-duration"),
    pytest.param(extractor.stop_after_run(), id="stop-after-run"),
    pytest.param(extractor.set_egg_timer(10000), id="egg-timer"),
    pytest.param(extractor.set_egg_timer_state(True), id="egg-timer-state"),
    pytest.param(cooktop.set_signal_volume(1), id="signal-volume"),
    pytest.param(cooktop.set_touch_sensitivity(1), id="sensitivity"),
]


@pytest.fixture
async def coordinator(hass):
    connection = Connection()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: False},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        result = BoraCoordinator(hass, entry)
    await result.async_refresh()
    # Isolate the coordinator boundary: command delivery is simulated, and no
    # setter reaches a transport or depends on another command's readback logic.
    result.device.execute = AsyncMock(return_value=result.data)
    yield result
    await result.async_close()


@pytest.mark.parametrize("command", COOKING_COMMANDS)
async def test_cooking_request_requires_option_without_caller_flag(coordinator, command):
    with pytest.raises(HomeAssistantError, match="Enable"):
        await coordinator.async_execute(command)
    coordinator.device.execute.assert_not_awaited()
    assert coordinator.last_update_success

    coordinator.cooking_enabled = True
    await coordinator.async_execute(command)
    coordinator.device.execute.assert_awaited_once_with(command)


@pytest.mark.parametrize("command", GENERAL_COMMANDS)
async def test_general_controls_do_not_require_cooking_option(coordinator, command):
    await coordinator.async_execute(command)
    coordinator.device.execute.assert_awaited_once_with(command)


@pytest.mark.parametrize("command", [cooktop.set_child_lock(3), extractor.set_power_level(3)])
async def test_cooking_option_never_bypasses_general_control_option(coordinator, command):
    coordinator.controls_enabled = False
    coordinator.cooking_enabled = True
    with pytest.raises(HomeAssistantError, match="Enable"):
        await coordinator.async_execute(command)
    coordinator.device.execute.assert_not_awaited()


async def test_explicit_cooking_flag_cannot_be_downgraded(coordinator):
    with pytest.raises(HomeAssistantError, match="Enable"):
        await coordinator.async_execute(extractor.set_power_level(3), cooking=True)
    coordinator.device.execute.assert_not_awaited()


async def test_malformed_pure_wrapper_is_rejected_before_delivery(coordinator):
    command = cooktop.PREFIX + "SetSpecificCooktopSetting", uint(1, 1)
    with pytest.raises(HomeAssistantError, match="Invalid BORA control request"):
        await coordinator.async_execute(command)
    coordinator.device.execute.assert_not_awaited()
    assert coordinator.last_update_success
