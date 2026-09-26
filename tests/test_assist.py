"""Explicit Assist starts on simulated peers; never operate a real appliance."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.ble import presets, zone
from custom_components.bora.ble.client import BoraDevice, CommandNotConfirmed, UnsupportedValue
from custom_components.bora.ble.transport import ConnectionLost
from custom_components.bora.ble.wire import Message, blob, string, uint
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator

UID = "front_left"
START_PATH = zone.SERVICE_PATH + "StartOrModifyCsf"


def program_status(uid, parameters, phase=2):
    csf = blob(1, parameters) + uint(2, phase)
    return blob(1, string(1, uid) + blob(2, blob(2, csf)))


class AssistConnection(Connection):
    def __init__(self):
        super().__init__()
        self.apply_start = True

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        if path == START_PATH:
            self.requests.append((path, body))
            if self.apply_start:
                request = Message(body)
                uid = request.text(2)
                self.responses[zone.get_status(uid)] = program_status(uid, request.bytes(1))
            return b""
        return await super().rpc(path, body, received=received, failed=failed)


@pytest.fixture
async def appliance():
    connection = AssistConnection()
    device = BoraDevice(connection)
    await device.initialize()
    yield device, connection
    await device.shutdown()


@pytest.mark.parametrize("preset_id", [62176, 62954, 63120, 63121])
async def test_explicit_catalogue_start_reads_before_and_after_one_write(appliance, preset_id):
    device, connection = appliance
    before = len(connection.requests)
    snapshot = await device.start_assist(UID, preset_id)
    requests = connection.requests[before:]
    writes = [index for index, (path, _) in enumerate(requests) if path == START_PATH]
    assert len(writes) == 1
    index = writes[0]
    assert index > 0
    assert index < len(requests) - 1
    assert all("/Get" in path for path, _ in requests[:index] + requests[index + 1:])
    assert requests[index] == presets.prepare_preset(
        device.information, device.descriptor, UID, preset_id, 0
    )
    program = snapshot["zones"][UID]["csf"]
    assert program["parameters"]["csf_id"] == preset_id
    assert program["parameters"]["csf_timer_duration"] == 0
    assert program["phase"] == 2  # Kept as confirmation_required, never auto-advanced.
    assert not any("Confirmation" in path or "SetBridged" in path for path, _ in requests)


async def test_start_rechecks_fresh_zone_state_before_transmitting(appliance):
    device, connection = appliance
    assert device.snapshot["zones"][UID]["power_level"] == 0
    # A physical control changed after the last cached snapshot.
    connection.responses[zone.get_status(UID)] = blob(1, string(1, UID) + blob(2, uint(1, 3)))
    with pytest.raises(UnsupportedValue, match="idle, unbridged"):
        await device.start_assist(UID, 62176)
    assert not any(path == START_PATH for path, _ in connection.requests)


@pytest.mark.parametrize(
    "changed",
    [
        {"power_level": 3},
        {"mode": "csf"},
        {"mode": "heat_retention"},
        {"bridged": True},
        {"bridged_to_uid": "back_left"},
        {"settings_present": False},
        {"power_level": None},
    ],
)
async def test_start_does_not_modify_an_active_bridged_or_unknown_zone(appliance, changed):
    device, connection = appliance
    device._state["zones"][UID].update(changed)
    before = list(connection.requests)
    with pytest.raises(UnsupportedValue):
        await device.start_assist(UID, 62176)
    assert connection.requests == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("csf_index", 1),
        ("csf_type", 3),
        ("csf_type_target_value", 140),
        ("csf_target_step_size", 10),
        ("csf_target_min_val", 100),
        ("csf_target_max_val", 240),
        ("csf_settings", 1),
        ("csf_timer_duration", 600000),
    ],
)
async def test_raw_route_cannot_change_the_known_catalogue_start(appliance, field, value):
    device, connection = appliance
    command = presets.prepare_preset(device.information, device.descriptor, UID, 62176, 0)
    parameters = zone.decode_csf_parameter(Message(command[1]).bytes(1))
    parameters.pop("present_fields")
    parameters.pop("csf_time_to_set_obsolete")
    parameters[field] = value
    before = list(connection.requests)
    with pytest.raises(UnsupportedValue):
        await device.execute(zone.start_or_modify_csf(UID, parameters))
    assert connection.requests == before


async def test_unobserved_start_is_not_retried_and_reconnect_does_not_start(appliance):
    device, connection = appliance
    connection.apply_start = False
    with pytest.raises(CommandNotConfirmed):
        await device.start_assist(UID, 62176)
    assert sum(path == START_PATH for path, _ in connection.requests) == 1
    await connection.disconnect()
    with pytest.raises(ConnectionLost):
        await device.start_assist(UID, 62176)
    await device.refresh()
    assert sum(path == START_PATH for path, _ in connection.requests) == 1


async def test_two_concurrent_starts_cannot_modify_the_first_program(appliance):
    device, connection = appliance
    outcomes = await asyncio.gather(
        device.start_assist(UID, 62176),
        device.start_assist(UID, 63120),
        return_exceptions=True,
    )
    assert sum(isinstance(item, dict) for item in outcomes) == 1
    assert sum(isinstance(item, UnsupportedValue) for item in outcomes) == 1
    assert sum(path == START_PATH for path, _ in connection.requests) == 1


async def test_unobserved_start_blocks_duplicates_across_reconnect(appliance):
    device, connection = appliance
    connection.apply_start = False
    command = presets.prepare_preset(device.information, device.descriptor, UID, 62176, 0)
    outcomes = await asyncio.gather(
        device.start_assist(UID, 62176), device.execute(command), return_exceptions=True
    )
    assert isinstance(outcomes[0], CommandNotConfirmed)
    assert isinstance(outcomes[1], UnsupportedValue)
    await connection.disconnect()
    await device.refresh()
    with pytest.raises(UnsupportedValue, match="pending or unconfirmed"):
        await device.start_assist(UID, 63120)
    assert sum(path == START_PATH for path, _ in connection.requests) == 1
    assert device.assist_start_blocked(UID)


async def test_cancelled_transmission_keeps_duplicate_start_blocked(appliance):
    device, connection = appliance
    transmitted = asyncio.Event()
    original_rpc = connection.rpc

    async def delayed_ack(path, body=b"", **kwargs):
        if path == START_PATH:
            connection.requests.append((path, body))
            transmitted.set()
            await asyncio.Future()
        return await original_rpc(path, body, **kwargs)

    connection.rpc = delayed_ack
    first = asyncio.create_task(device.start_assist(UID, 62176))
    await transmitted.wait()
    command = presets.prepare_preset(device.information, device.descriptor, UID, 63120, 0)
    with pytest.raises(UnsupportedValue, match="pending or unconfirmed"):
        await device.execute(command)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    await device.refresh()
    with pytest.raises(UnsupportedValue, match="pending or unconfirmed"):
        await device.execute(command)
    assert sum(path == START_PATH for path, _ in connection.requests) == 1


@pytest.mark.parametrize("use_stream", [False, True])
async def test_only_matching_program_observation_resolves_uncertain_start(appliance, use_stream):
    device, connection = appliance
    connection.apply_start = False
    command = presets.prepare_preset(device.information, device.descriptor, UID, 62176, 0)
    other = presets.prepare_preset(device.information, device.descriptor, UID, 63120, 0)
    with pytest.raises(CommandNotConfirmed):
        await device.start_assist(UID, 62176)

    async def observe(body):
        if use_stream:
            connection.streams[zone.STREAM_PATH](body)
        else:
            connection.responses[zone.get_status(UID)] = body
            await device.refresh()

    await observe(program_status(UID, Message(other[1]).bytes(1)))
    assert device.assist_start_blocked(UID)
    await observe(program_status(UID, Message(command[1]).bytes(1), phase=99))
    assert device.assist_start_blocked(UID)
    await observe(program_status(UID, Message(command[1]).bytes(1)))
    assert not device.assist_start_blocked(UID)
    # Resolving the uncertainty never authorizes modifying an active program.
    with pytest.raises(UnsupportedValue, match="idle, unbridged"):
        await device.start_assist(UID, 63120)
    assert sum(path == START_PATH for path, _ in connection.requests) == 1


async def test_cancel_before_write_does_not_leave_uncertain_start(appliance):
    device, connection = appliance
    checking = asyncio.Event()

    async def delayed_preflight():
        checking.set()
        await asyncio.Future()

    with patch.object(device, "_read_statuses", side_effect=delayed_preflight):
        first = asyncio.create_task(device.start_assist(UID, 62176))
        await checking.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
    assert not device.assist_start_blocked(UID)
    assert not any(path == START_PATH for path, _ in connection.requests)
    await device.start_assist(UID, 62176)


async def test_ha_selection_is_local_and_only_explicit_start_operates(hass):
    connection = AssistConnection()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: True},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    await coordinator.async_refresh()
    try:
        before = list(connection.requests)
        assert coordinator.assist_selections == {}
        with pytest.raises(HomeAssistantError, match="Choose"):
            await coordinator.async_start_assist(UID)
        coordinator.select_assist(UID, 62176)
        assert coordinator.assist_selections[UID] == 62176
        assert connection.requests == before
        coordinator.cooking_enabled = False
        with pytest.raises(HomeAssistantError, match="Enable"):
            await coordinator.async_start_assist(UID)
        assert connection.requests == before
        coordinator.cooking_enabled = True
        await coordinator.async_start_assist(UID)
        assert sum(path == START_PATH for path, _ in connection.requests) == 1
        assert coordinator.data["zones"][UID]["csf"]["phase"] == 2
    finally:
        await coordinator.async_close()


async def test_rejected_fresh_preflight_updates_ha_with_actual_zone_status(hass):
    connection = AssistConnection()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: True},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    await coordinator.async_refresh()
    try:
        coordinator.select_assist(UID, 62176)
        connection.responses[zone.get_status(UID)] = blob(1, string(1, UID) + blob(2, uint(1, 3)))
        with pytest.raises(HomeAssistantError, match="idle, unbridged"):
            await coordinator.async_start_assist(UID)
        assert coordinator.last_update_success
        assert coordinator.data["zones"][UID]["power_level"] == 3
        assert not any(path == START_PATH for path, _ in connection.requests)
    finally:
        await coordinator.async_close()
