"""Explicit favorite reads and cache lifetime, exclusively on a fake peer."""

import asyncio
from datetime import datetime
from unittest.mock import Mock

import pytest
from test_client import Connection
from test_diagnostics import successful_responses

from custom_components.bora.ble import identify
from custom_components.bora.ble.client import BoraDevice, UnsupportedValue
from custom_components.bora.ble.transport import ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import ProtocolError, Stream, blob, uint

SAVED = identify.get_saved_csf()
POPULATED = blob(1, uint(1, 62176) + uint(3, 3) + uint(4, 2))


class SavedConnection(Connection):
    def __init__(self):
        super().__init__()
        self.saved_reply = POPULATED
        for path, body in successful_responses().items():
            self.responses[(path, b"")] = body
        self.responses[identify.list_sys_events()] = successful_responses()[
            identify.list_sys_events()[0]
        ]
        self.responses[identify.list_user_events()] = successful_responses()[
            identify.list_user_events()[0]
        ]

    async def rpc(self, path, body=b"", **kwargs):
        if (path, body) == SAVED:
            self.requests.append((path, body))
            if isinstance(self.saved_reply, BaseException):
                raise self.saved_reply
            return self.saved_reply
        return await super().rpc(path, body, **kwargs)


@pytest.fixture
async def appliance():
    connection = SavedConnection()
    changed = Mock()
    device = BoraDevice(connection, favorites_updated=changed)
    await device.initialize()
    yield device, connection, changed
    await device.shutdown()


async def test_only_explicit_read_fills_cache_and_returns_detached_snapshot(appliance):
    device, connection, _ = appliance
    assert device.favorites_snapshot is None
    await device.refresh()
    assert SAVED not in connection.requests
    before = len(connection.requests)
    snapshot = await device.refresh_favorites()
    assert connection.requests[before:] == [SAVED]
    assert snapshot["slots"][3]["label"] == "Cook egg dishes"
    assert snapshot["slots"][4]["label"] == "empty"
    assert datetime.fromisoformat(snapshot["read_at"]).utcoffset().total_seconds() == 0
    snapshot["slots"][3]["parameters"]["csf_id"] = 999
    assert device.favorites_snapshot["slots"][3]["parameters"]["csf_id"] == 62176
    await device.refresh()
    assert connection.requests.count(SAVED) == 1


async def test_successful_empty_response_is_different_from_unknown(appliance):
    device, connection, _ = appliance
    connection.saved_reply = b""
    result = await device.refresh_favorites()
    assert {item["state"] for item in result["slots"].values()} == {"empty"}


@pytest.mark.parametrize(
    "reply,error",
    [
        (RpcError(12), RpcError),
        (RequestTimeout("fixture timeout"), RequestTimeout),
        (b"\x0a\x80", ProtocolError),
        (asyncio.CancelledError(), asyncio.CancelledError),
    ],
)
async def test_failed_or_cancelled_read_clears_old_values_and_diagnostics(appliance, reply, error):
    device, connection, changed = appliance
    await device.refresh_favorites()
    assert device.diagnostic_snapshot["saved_csf"]["status"] == "ok"
    before = connection.requests.count(SAVED)
    changed.reset_mock()
    connection.saved_reply = reply
    with pytest.raises(error):
        await device.refresh_favorites()
    assert device.favorites_snapshot is None
    assert "saved_csf" not in device.diagnostic_snapshot
    assert connection.connected
    assert connection.requests.count(SAVED) == before + 1
    changed.assert_called_once_with()


async def test_new_read_invalidates_display_before_waiting_for_response(appliance):
    device, connection, changed = appliance
    await device.refresh_favorites()
    started = asyncio.Event()
    original_rpc = connection.rpc

    async def delayed(path, body=b"", **kwargs):
        if (path, body) == SAVED:
            started.set()
            await asyncio.Future()
        return await original_rpc(path, body, **kwargs)

    connection.rpc = delayed
    changed.reset_mock()
    reading = asyncio.create_task(device.refresh_favorites())
    await started.wait()
    assert device.favorites_snapshot is None
    changed.assert_called_once_with()
    reading.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reading
    assert device.favorites_snapshot is None


async def test_cancellation_while_waiting_for_lock_does_not_invalidate_current_cache(appliance):
    device, _, changed = appliance
    before = await device.refresh_favorites()
    changed.reset_mock()
    await device._lock.acquire()
    try:
        reading = asyncio.create_task(device.refresh_favorites())
        await asyncio.sleep(0)
        reading.cancel()
        with pytest.raises(asyncio.CancelledError):
            await reading
        assert device.favorites_snapshot == before
        changed.assert_not_called()
    finally:
        device._lock.release()


@pytest.mark.parametrize("method", ["close", "initialize"])
async def test_explicit_close_or_reinitialize_discards_cache_without_getting_it_again(
    appliance, method
):
    device, connection, _ = appliance
    await device.refresh_favorites()
    await getattr(device, method)()
    await device.refresh()
    assert device.favorites_snapshot is None
    assert "saved_csf" not in device.diagnostic_snapshot
    assert connection.requests.count(SAVED) == 1


@pytest.mark.parametrize("method", ["refresh_favorites", "collect_diagnostics"])
async def test_late_response_cannot_restore_cache_after_connection_invalidation(appliance, method):
    device, connection, _ = appliance
    original_rpc = connection.rpc

    async def stale_response(path, body=b"", **kwargs):
        result = await original_rpc(path, body, **kwargs)
        if (path, body) == SAVED:
            # The old response was delivered just before connection turnover.
            device.invalidate_favorites()
            await connection.disconnect()
            await connection.connect()
        return result

    connection.rpc = stale_response
    with pytest.raises(ConnectionLost, match="earlier connection"):
        await getattr(device, method)()
    assert device.favorites_snapshot is None
    assert "saved_csf" not in device.diagnostic_snapshot
    assert connection.requests.count(SAVED) == 1


async def test_diagnostics_uses_its_single_saved_read_to_update_the_same_display(appliance):
    device, connection, _ = appliance
    before = len(connection.requests)
    result = await device.collect_diagnostics()
    assert len(connection.requests[before:]) == 6
    assert connection.requests[before:].count(SAVED) == 1
    assert result["saved_csf"]["data"][0]["csf_id"] == 62176
    assert device.favorites_snapshot["slots"][3]["label"] == "Cook egg dishes"
    connection.saved_reply = RpcError(12, request_id=1, path=SAVED[0], stream=Stream.NONE)
    result = await device.collect_diagnostics()
    assert result["saved_csf"]["status"] == "unsupported"
    assert device.favorites_snapshot is None


async def test_diagnostics_and_explicit_read_serialize_without_extra_gets(appliance):
    device, connection, _ = appliance
    before = len(connection.requests)
    await asyncio.gather(device.collect_diagnostics(), device.refresh_favorites())
    requests = connection.requests[before:]
    assert len(requests) == 7
    assert requests.count(SAVED) == 2  # One read per explicit request, never a follow-up read.
    assert requests[-2:] == [SAVED, SAVED]
    assert device.favorites_snapshot["slots"][3]["state"] == "known"


async def test_unestablished_device_is_not_queried(appliance):
    device, connection, _ = appliance
    device.information["product"] = 99
    before = list(connection.requests)
    with pytest.raises(UnsupportedValue):
        await device.refresh_favorites()
    assert connection.requests == before
