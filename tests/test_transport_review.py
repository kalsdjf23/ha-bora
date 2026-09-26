"""Independent offline regression reproductions for lifecycle/state review."""

import asyncio

import pytest
from test_client import Connection
from test_transport import Factory

from custom_components.bora.ble import extractor, zone
from custom_components.bora.ble.client import BoraDevice, UnsupportedValue
from custom_components.bora.ble.transport import BrpcConnection
from custom_components.bora.ble.wire import blob, string, uint


async def test_review_poll_does_not_overwrite_newer_zone_stream_update():
    connection = Connection()
    device = BoraDevice(connection)
    await device.initialize()
    first, *_, last = device.zone_uids
    original_rpc = connection.rpc

    async def interleaved_rpc(path, body=b"", **kwargs):
        if (path, body) == zone.get_status(last):
            # First zone was already read at zero. While reading the last zone,
            # its newer stream update reports seven. The completed poll must
            # not roll the first zone back to its earlier value.
            settings = string(1, first) + blob(2, uint(1, 7))
            connection.streams[zone.STREAM_PATH](blob(1, settings))
        return await original_rpc(path, body, **kwargs)

    connection.rpc = interleaved_rpc
    try:
        snapshot = await device.refresh()
        assert snapshot["zones"][first]["power_level"] == 7
    finally:
        await device.close()


async def test_review_cancellation_during_stream_stop_still_closes_gatt():
    factory = Factory()
    connection = BrpcConnection(factory, timeout=0.2)
    await connection.connect()
    peer = factory.peers[-1]
    await connection.subscribe("/fixture/StreamStatus", lambda _: None)
    peer.respond = False
    stop_written = asyncio.Event()
    original_write = peer.write_gatt_char

    async def observed_write(uuid, data, response):
        await original_write(uuid, data, response)
        if len(peer.requests) >= 2:
            stop_written.set()

    peer.write_gatt_char = observed_write
    stopping = asyncio.create_task(connection.disconnect())
    await stop_written.wait()
    stopping.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert not connection.connected
        assert not peer.is_connected
    finally:
        await connection.disconnect()


async def test_review_extractor_manual_mode_requires_its_advertised_capability():
    connection = Connection()
    device = BoraDevice(connection)
    await device.initialize()
    try:
        device.descriptor["extractor_descriptor"]["extractor_mode_types"] = [1]
        with pytest.raises(UnsupportedValue):
            device.validate_command(extractor.set_power_level(3))
    finally:
        await device.close()


async def test_review_queued_refresh_cannot_reconnect_after_coordinator_shutdown(hass):
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.bora.const import DOMAIN
    from custom_components.bora.coordinator import BoraCoordinator

    connection = Connection()
    entry = MockConfigEntry(domain=DOMAIN, data={"address": "AA:BB:CC:DD:EE:FF"})
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    await coordinator.device.initialize()
    try:
        async with coordinator.device._lock:
            pending = asyncio.create_task(coordinator.async_refresh())
            await asyncio.sleep(
                0
            )  # Refresh passes the HA shutdown check, then waits for device lock.
            await coordinator.async_close()
            assert not connection.connected
        await pending
        assert not connection.connected
        assert connection.connect_count == 1
    finally:
        await coordinator.device.close()


def test_review_escaped_input_cannot_bypass_frame_size_limit():
    from custom_components.bora.ble.wire import MAX_FRAME_SIZE, FrameDecoder, ProtocolError

    decoder = FrameDecoder()
    with pytest.raises(ProtocolError, match="large"):
        decoder.feed(b"\x7e" + b"\x7d\x5e" * (MAX_FRAME_SIZE + 1))
    assert not decoder.incomplete


async def test_review_stream_received_with_poll_reply_wins_before_waiter_resumes():
    connection = Connection()
    device = BoraDevice(connection)
    await device.initialize()
    original_rpc = connection.rpc

    async def interleaved_rpc(path, body=b"", **kwargs):
        response = await original_rpc(path, body, **kwargs)
        if (path, body) == extractor.get_status():
            # The transport can receive a unary reply followed by CONTINUE in
            # the same notification: the future is resolved, then the stream
            # callback runs, before the awaiting poll resumes with the reply.
            newer = blob(1, blob(2, uint(2, 7)))
            connection.streams[extractor.STREAM_PATH](newer)
        return response

    connection.rpc = interleaved_rpc
    try:
        snapshot = await device.refresh()
        assert snapshot["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 7
    finally:
        await device.close()
