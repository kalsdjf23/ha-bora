"""Explicit Wi-Fi snapshots expire with failed reads and connection lifetime."""

import asyncio
import json
from datetime import datetime
from unittest.mock import Mock

import pytest
from test_favorites_client import SAVED, SavedConnection

from custom_components.bora.ble import identify
from custom_components.bora.ble.client import BoraDevice
from custom_components.bora.ble.transport import ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream, blob, string, uint

WIFI = identify.get_wifi_status()


@pytest.fixture
async def appliance():
    connection = SavedConnection()
    changed = Mock()
    device = BoraDevice(connection, diagnostics_updated=changed)
    await device.initialize()
    changed.reset_mock()
    yield device, connection, changed
    await device.shutdown()


async def test_only_explicit_diagnostics_read_populates_identifier_free_snapshot(appliance):
    device, connection, changed = appliance
    assert device.wifi_snapshot is None
    await device.refresh()
    assert WIFI not in connection.requests
    connection.responses[WIFI] = blob(
        1, uint(1, 9) + string(2, "PRIVATE_WIFI") + blob(3, b"\xaa\xbb\xcc\xdd\xee\xff")
        + uint(4, 0xC0000201) + string(5, "PRIVATE_TIME_ZONE"),
    )
    before = len(connection.requests)
    result = await device.collect_diagnostics()
    assert len(connection.requests[before:]) == 6
    assert connection.requests[before:].count(WIFI) == 1
    snapshot = device.wifi_snapshot
    assert snapshot == {
        "connection_status": 9, "connection_status_name": "internet_access",
        "read_at": result["wifi_status"]["read_at"],
    }
    assert datetime.fromisoformat(snapshot["read_at"]).utcoffset().total_seconds() == 0
    assert "PRIVATE" not in json.dumps(snapshot)
    snapshot["connection_status"] = -1
    result["wifi_status"]["data"]["connection_status"] = -2
    assert device.wifi_snapshot["connection_status"] == 9
    assert changed.call_count == 2  # Clear old value, then publish the completed read.
    await device.refresh()
    await device.refresh_favorites()
    assert connection.requests.count(WIFI) == 1
    assert device.wifi_snapshot["connection_status"] == 9


@pytest.mark.parametrize("reply", [
    RpcError(12, request_id=1, path=WIFI[0], stream=Stream.NONE),
    RequestTimeout("private backend text"),
    b"\x0a\x80",
    b"",  # A missing wrapper must not synthesize an unspecified/off status.
])
async def test_failed_or_absent_wifi_read_clears_previous_display(appliance, reply):
    device, connection, changed = appliance
    await device.collect_diagnostics()
    assert device.wifi_snapshot is not None
    before = connection.requests.count(WIFI)
    changed.reset_mock()
    connection.responses[WIFI] = reply
    await device.collect_diagnostics()
    assert device.wifi_snapshot is None
    assert connection.requests.count(WIFI) == before + 1
    changed.assert_called_once_with()


@pytest.mark.parametrize(
    "code,name", [(0, "unspecified"), (8, "no_internet"), (999, "unknown_999")],
)
async def test_present_status_preserves_unspecified_distinct_and_unknown_values(
    appliance, code, name,
):
    device, connection, _ = appliance
    connection.responses[WIFI] = blob(1, uint(1, code))
    await device.collect_diagnostics()
    assert device.wifi_snapshot["connection_status"] == code
    assert device.wifi_snapshot["connection_status_name"] == name


async def test_cancelled_wifi_refresh_clears_cache_before_waiting(appliance):
    device, connection, changed = appliance
    await device.collect_diagnostics()
    started = asyncio.Event()
    original_rpc = connection.rpc

    async def blocking_rpc(path, body=b"", **kwargs):
        if (path, body) == WIFI:
            started.set()
            await asyncio.Event().wait()
        return await original_rpc(path, body, **kwargs)

    connection.rpc = blocking_rpc
    changed.reset_mock()
    collecting = asyncio.create_task(device.collect_diagnostics())
    await started.wait()
    assert device.wifi_snapshot is None
    assert "wifi_status" not in device.diagnostic_snapshot
    changed.assert_called_once_with()
    collecting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await collecting
    assert device.wifi_snapshot is None


@pytest.mark.parametrize("action", ["reinitialize", "reconnect", "close", "shutdown"])
async def test_connection_lifecycle_never_restores_old_wifi_state(appliance, action):
    device, connection, changed = appliance
    await device.collect_diagnostics()
    count = connection.requests.count(WIFI)
    changed.reset_mock()
    if action == "reinitialize":
        await device.initialize()
    elif action == "reconnect":
        await connection.disconnect()
        assert device.wifi_snapshot is None
        await device.refresh()
    else:
        await getattr(device, action)()
    assert device.wifi_snapshot is None
    assert "wifi_status" not in device.diagnostic_snapshot
    assert connection.requests.count(WIFI) == count
    assert changed.called


async def test_late_wifi_result_cannot_restore_invalidated_snapshot(appliance):
    device, connection, _ = appliance
    original_rpc = connection.rpc

    async def stale_response(path, body=b"", **kwargs):
        result = await original_rpc(path, body, **kwargs)
        if (path, body) == WIFI:
            device.invalidate_wifi()
        return result

    connection.rpc = stale_response
    with pytest.raises(ConnectionLost, match="earlier connection"):
        await device.collect_diagnostics()
    assert device.wifi_snapshot is None
    assert "wifi_status" not in device.diagnostic_snapshot
    assert connection.requests.count(WIFI) == 1
    assert device.favorites_snapshot is None
    assert "saved_csf" not in device.diagnostic_snapshot


@pytest.mark.parametrize("product", [1, 2])
async def test_disconnect_after_successful_wifi_reply_does_not_publish_it(appliance, product):
    device, connection, _ = appliance
    device.information["product"] = product  # Exercise both optional cache commit paths.
    original_rpc = connection.rpc

    async def disconnect_after_queries(path, body=b"", **kwargs):
        result = await original_rpc(path, body, **kwargs)
        if (path, body) == SAVED:
            await connection.disconnect()
        return result

    connection.rpc = disconnect_after_queries
    with pytest.raises(ConnectionLost):
        await device.collect_diagnostics()
    assert device.wifi_snapshot is None
    assert "wifi_status" not in device.diagnostic_snapshot
    assert "saved_csf" not in device.diagnostic_snapshot
    assert connection.requests.count(WIFI) == 1
