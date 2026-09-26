"""Keep after-run readable when a zone returns the observed UNAVAILABLE reply."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection
from test_entities import entity_for

from custom_components.bora import fan, sensor
from custom_components.bora.ble import cooktop, extractor, zone
from custom_components.bora.ble.client import BoraDevice, CommandNotConfirmed, UnsupportedValue
from custom_components.bora.ble.transport import ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import ProtocolError, Response, blob, string, uint
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator

UID = "front_left"


def observed(kind):
    data = json.loads(
        (Path(__file__).parent / "fixtures/x_pure_cooking_2026_09_26.json").read_text()
    )
    return Response.decode(bytes.fromhex(data["responses"][kind]["response_payload_hex"]))


def unavailable():
    reply = observed("zone_unavailable")
    assert reply.code == 14
    return RpcError(reply.code, reply.error)


@pytest.fixture
async def appliance():
    connection = Connection()
    device = BoraDevice(connection)
    await device.initialize()
    yield device, connection
    await device.shutdown()


def test_recorded_cooking_and_after_run_payloads_decode():
    active = zone.decode_status(observed("back_left_power_7").body)
    inactive = zone.decode_status(observed("back_left_power_0").body)
    assert active["uid"] == inactive["uid"] == "back_left"
    assert active["power_level"] == 7
    assert inactive["power_level"] == 0
    after_run = extractor.decode_status(observed("after_run_start").body)
    assert after_run["extractor_settings"]["extractor_mode"]["power_level"] == 1
    assert after_run["remaining_after_run_ms"] == 1800000


async def test_observed_zone_error_discards_stale_status_and_preserves_after_run(appliance):
    device, connection = appliance
    device._state["zones"][UID]["power_level"] = 7
    connection.responses[zone.get_status(UID)] = unavailable()
    connection.responses[extractor.get_status()] = observed("after_run_start").body
    before = len(connection.requests)
    snapshot = await device.refresh()
    assert UID not in snapshot["zones"]  # Unknown, not a synthesized zero.
    assert set(snapshot["zones"]) == set(device.zone_uids) - {UID}
    assert snapshot["extractor"]["remaining_after_run_ms"] == 1800000
    assert snapshot["cooktop"] is not None
    assert connection.requests[before:] == [
        extractor.get_status(), cooktop.get_status(),
        *(zone.get_status(uid) for uid in device.zone_uids),
    ]
    assert connection.connected and connection.connect_count == 1
    assert len(connection.streams) == 3


async def test_all_zones_unavailable_during_initialization_can_recover_by_read_and_stream():
    connection = Connection()
    original = dict(connection.responses)
    for uid in ("front_left", "back_left", "back_right", "front_right"):
        connection.responses[zone.get_status(uid)] = unavailable()
    device = BoraDevice(connection)
    try:
        snapshot = await device.initialize()
        assert snapshot["zones"] == {}
        assert snapshot["extractor"] and snapshot["cooktop"]
        connection.responses[zone.get_status(UID)] = original[zone.get_status(UID)]
        assert set((await device.refresh())["zones"]) == {UID}
        connection.streams[zone.STREAM_PATH](observed("back_left_power_7").body)
        assert device.snapshot["zones"]["back_left"]["power_level"] == 7
        assert connection.connect_count == 1
    finally:
        await device.shutdown()


@pytest.mark.parametrize(
    "reply", [RpcError(7), RpcError(12), RequestTimeout("timeout"),
              ConnectionLost("lost"), b"\x0a\x80"],
    ids=["permission", "unsupported", "timeout", "disconnect", "malformed"],
)
async def test_other_zone_failures_still_propagate(appliance, reply):
    device, connection = appliance
    connection.responses[zone.get_status(UID)] = reply
    expected = type(reply) if isinstance(reply, Exception) else ProtocolError
    with pytest.raises(expected):
        await device.refresh()


@pytest.mark.parametrize("command", [extractor.get_status(), cooktop.get_status()])
async def test_unavailable_on_core_status_still_propagates(appliance, command):
    device, connection = appliance
    connection.responses[command] = unavailable()
    with pytest.raises(RpcError):
        await device.refresh()


async def test_unavailable_without_valid_ordered_unary_callback_still_propagates(appliance):
    device, connection = appliance
    original = connection.rpc

    async def wrong_reply(path, body=b"", **kwargs):
        if (path, body) == zone.get_status(UID):
            # The transport does not deliver a unary error callback for an
            # invalid streaming response to this unary request.
            raise unavailable()
        return await original(path, body, **kwargs)

    connection.rpc = wrong_reply
    with pytest.raises(RpcError):
        await device.refresh()


@pytest.mark.parametrize("stream_after_error", [True, False])
async def test_zone_recovery_stream_respects_error_arrival_order(appliance, stream_after_error):
    device, connection = appliance
    original = connection.rpc
    connection.responses[zone.get_status(UID)] = unavailable()
    update = blob(1, string(1, UID) + blob(2, uint(1, 3)))

    async def combined_reply(path, body=b"", **kwargs):
        if (path, body) != zone.get_status(UID):
            return await original(path, body, **kwargs)
        if not stream_after_error:
            connection.streams[zone.STREAM_PATH](update)
        try:
            return await original(path, body, **kwargs)
        except RpcError:
            if stream_after_error:
                connection.streams[zone.STREAM_PATH](update)
            raise

    connection.rpc = combined_reply
    snapshot = await device.refresh()
    if stream_after_error:
        assert snapshot["zones"][UID]["power_level"] == 3
    else:
        assert UID not in snapshot["zones"]


@pytest.mark.parametrize("last_unavailable", [True, False])
async def test_disconnect_after_final_reply_cannot_turn_refresh_into_success(
    appliance, last_unavailable
):
    device, connection = appliance
    last = zone.get_status(device.zone_uids[-1])
    if last_unavailable:
        connection.responses[last] = unavailable()
    original = connection.rpc

    async def disconnected_after_reply(path, body=b"", **kwargs):
        try:
            return await original(path, body, **kwargs)
        finally:
            if (path, body) == last:
                await connection.disconnect()

    connection.rpc = disconnected_after_reply
    with pytest.raises(ConnectionLost):
        await device.refresh()
    assert not connection.connected


@pytest.mark.parametrize("command", [
    zone.set_power(UID, 3), zone.set_timer(UID, 1000),
    zone.set_timer_state(UID, True), zone.stop_csf(UID),
])
async def test_waiting_zone_control_rechecks_status_under_lock(appliance, command):
    device, connection = appliance
    await device._lock.acquire()
    task = asyncio.create_task(device.execute(command))
    await asyncio.sleep(0)
    assert not task.done()
    # Simulate a preceding refresh completing with this zone unavailable.
    device._state["zones"].pop(UID)
    before = list(connection.requests)
    device._lock.release()
    with pytest.raises(UnsupportedValue, match="status is unavailable"):
        await task
    assert connection.requests == before


async def test_missing_readback_cannot_confirm_zone_write_or_replay_it(appliance):
    device, connection = appliance
    command = zone.set_power(UID, 3)
    connection.responses[command] = b""
    connection.responses[zone.get_status(UID)] = unavailable()
    with pytest.raises(CommandNotConfirmed):
        await device.execute(command)
    assert UID not in device.snapshot["zones"]
    assert connection.requests.count(command) == 1
    with pytest.raises(UnsupportedValue):
        await device.execute(command)
    assert connection.requests.count(command) == 1


async def test_extractor_readback_is_confirmed_even_when_zone_is_unavailable(appliance):
    device, connection = appliance
    connection.responses[zone.get_status(UID)] = unavailable()
    command = extractor.set_power_level(3)
    result = await device.execute(command)
    assert result["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 3
    assert UID not in result["zones"]
    assert connection.requests.count(command) == 1


async def test_ha_keeps_extraction_available_and_recovers_zone_entities(hass):
    connection = Connection()
    entry = MockConfigEntry(
        domain=DOMAIN, data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: True},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    try:
        await coordinator.async_refresh()
        power = entity_for(sensor, coordinator, f"{UID}_power")
        fan_entity = fan.build_entities(coordinator)[0]
        connection.responses[zone.get_status(UID)] = unavailable()
        await coordinator.async_refresh()
        assert coordinator.last_update_success and connection.connected
        assert fan_entity.available
        assert not power.available and power.native_value is None
        before = list(connection.requests)
        with pytest.raises(HomeAssistantError, match="status is unavailable"):
            await coordinator.async_execute(zone.set_power(UID, 3), cooking=True)
        assert connection.requests == before
        assert coordinator.last_update_success
        connection.streams[zone.STREAM_PATH](blob(1, string(1, UID) + blob(2, uint(1, 3))))
        assert power.available and power.native_value == 3
    finally:
        await coordinator.async_close()
