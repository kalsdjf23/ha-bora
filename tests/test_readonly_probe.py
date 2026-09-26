"""Run the developer probe exclusively against simulated peers."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from bleak.exc import BleakError
from test_client import Connection, recorded_responses
from test_favorites_client import POPULATED, SavedConnection
from test_transport import Factory

from custom_components.bora.ble import identify, zone
from custom_components.bora.ble.transport import ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream
from scripts.readonly_probe import READ_PATHS, TRACE_LIMIT, ReadOnlyConnection, observe


async def test_probe_records_sanitized_reads_and_leaves_no_connection():
    connection = Connection()
    report, failed = await observe(connection, address="AA:BB:CC:DD:EE:FF", seconds=0)
    assert not failed
    assert not connection.connected
    assert not connection.streams
    assert all(path in READ_PATHS for path, _ in connection.requests)
    probe = report["diagnostic_snapshot"]["probe"]
    assert probe["status"] == "completed"
    assert probe["status_updates_including_snapshots"] == 2
    assert len(probe["observations"]) == 2
    assert "AA:BB:CC:DD:EE:FF" not in json.dumps(report)


@pytest.mark.parametrize("saved_reply", [POPULATED, b"", RpcError(12)])
async def test_extended_probe_preserves_saved_read_in_report_after_shutdown(saved_reply):
    connection = SavedConnection()
    connection.saved_reply = saved_reply
    report, failed = await observe(
        connection, address="AA:BB:CC:DD:EE:FF", seconds=0, extended=True
    )
    assert not failed
    assert not connection.connected
    assert not connection.streams
    optional = report["diagnostic_snapshot"]["optional_reads"]
    assert len(optional) == 6
    expected = (
        {"status": "unsupported", "code": 12}
        if isinstance(saved_reply, RpcError)
        else {"status": "ok", "data": identify.decode_saved_csf(saved_reply)}
    )
    assert optional["saved_csf"] == json.loads(json.dumps(expected))
    assert connection.requests.count(identify.get_saved_csf()) == 1
    assert all(path in READ_PATHS for path, _ in connection.requests)
    assert "AA:BB:CC:DD:EE:FF" not in json.dumps(report)


async def test_probe_boundary_rejects_actuators_and_confirmation_before_io():
    factory = Factory()
    connection = ReadOnlyConnection(factory)
    for path in (
        "/bora.generic.zone.v1.ZoneService/SetMode",
        "/bora.generic.connection.v1.ConnectionService/GetUserConfirmation",
        "/bora.generic.debug.v1.DebugService/InvokeFactoryReset",
    ):
        with pytest.raises(ValueError):
            await connection.rpc(path)
    with pytest.raises(ValueError):
        await connection.subscribe("/unknown/StreamStatus", lambda _: None)
    assert not factory.peers
    assert connection.request_trace == {"total": 0, "omitted": 0, "requests": []}


async def test_cancelled_probe_always_disconnects():
    connection = Connection()
    started = asyncio.Event()

    async def blocked(**kwargs):
        connection.connected = True
        started.set()
        await asyncio.Event().wait()

    connection.connect = blocked
    connection.disconnect = AsyncMock(side_effect=connection.disconnect)
    task = asyncio.create_task(observe(connection, address="fixture", seconds=10))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not connection.connected
    assert connection.disconnect.await_count >= 1


async def test_backend_error_produces_a_private_safe_failed_report():
    connection = Connection()
    connection.connect = AsyncMock(side_effect=BleakError("Private address AA:BB:CC:DD:EE:FF"))
    report, failed = await observe(connection, address="AA:BB:CC:DD:EE:FF", seconds=0)
    assert failed
    assert not connection.connected
    assert report["diagnostic_snapshot"]["probe"]["error_type"] == "BleakError"
    assert "Private address" not in json.dumps(report)
    assert "AA:BB:CC:DD:EE:FF" not in json.dumps(report)


@pytest.mark.parametrize("seconds", [-1, 301, 1.5, True])
async def test_invalid_duration_cannot_start_a_connection(seconds):
    connection = Connection()
    with pytest.raises(ValueError):
        await observe(connection, address="fixture", seconds=seconds)
    assert connection.connect_count == 0


async def test_trace_correlates_zone_error_and_stream_cleanup_without_raw_errors():
    factory = Factory()
    connection = ReadOnlyConnection(factory)
    await connection.connect()
    peer = factory.peers[0]
    stream_id = await connection.subscribe(zone.STREAM_PATH, lambda _: None)
    peer.respond = False
    peer.request_seen.clear()
    pending = asyncio.create_task(connection.rpc(*zone.get_status("front_left")))
    await peer.request_seen.wait()
    request_id = peer.requests[-1].uint(3)
    peer.code = 14
    peer.reply(request_id, error=b"private error AA:BB:CC:DD:EE:FF")
    with pytest.raises(RpcError):
        await pending
    peer.code = 0
    peer.respond = True
    await connection.disconnect()
    trace = connection.request_trace
    start, failed, stop = trace["requests"]
    assert trace["total"] == 3 and trace["omitted"] == 0
    assert [row["operation"] for row in trace["requests"]] == [
        "stream_start", "read", "stream_stop"
    ]
    assert start["request_id"] == stop["request_id"] == stream_id
    assert start["stream"] == "START" and stop["stream"] == "STOP"
    assert failed["request_id"] == request_id
    assert failed["path"] == zone.GET_PATH and failed["zone_uid"] == "front_left"
    assert failed["outcome"] == "error" and failed["error_type"] == "RpcError"
    assert failed["response_code"] == 14
    assert all(row["started_at"] <= row["finished_at"] for row in trace["requests"])
    assert "private error" not in json.dumps(trace)
    failed["response_code"] = 999
    assert connection.request_trace["requests"][1]["response_code"] == 14


@pytest.mark.parametrize("failure", ["timeout", "disconnect", "cancel"])
async def test_trace_records_uncertain_exchange_without_claiming_a_response(failure):
    factory = Factory()
    connection = ReadOnlyConnection(factory, timeout=0.05)
    await connection.connect()
    peer = factory.peers[0]
    peer.respond = False
    task = asyncio.create_task(connection.rpc(*zone.get_status("back_left")))
    await peer.request_seen.wait()
    if failure == "disconnect":
        await peer.disconnect()
    elif failure == "cancel":
        task.cancel()
    expected = {"timeout": RequestTimeout, "disconnect": ConnectionLost,
                "cancel": asyncio.CancelledError}[failure]
    with pytest.raises(expected):
        await task
    await connection.disconnect()
    row, = connection.request_trace["requests"]
    assert row["outcome"] == ("cancelled" if failure == "cancel" else "error")
    assert "response_code" not in row and "stream" not in row
    assert "finished_at" in row
    assert len(peer.requests) == 1


async def test_trace_bounds_history_and_reports_omissions():
    factory = Factory()
    connection = ReadOnlyConnection(factory)
    await connection.connect()
    for _ in range(TRACE_LIMIT + 5):
        await connection.rpc(*zone.get_status("front_left"))
    await connection.disconnect()
    trace = connection.request_trace
    assert trace["total"] == TRACE_LIMIT + 5 and trace["omitted"] == 5
    assert len(trace["requests"]) == TRACE_LIMIT
    assert [row["sequence"] for row in trace["requests"]] == [
        1, *range(7, TRACE_LIMIT + 6)
    ]


async def test_report_includes_transport_requests_and_cleanup_after_zone_unavailable():
    factory = Factory()
    responses = recorded_responses()

    async def connect(callback):
        peer = await factory(callback)
        original_reply = peer.reply

        def replay(request_id, *, stream=Stream.NONE, **kwargs):
            if stream != Stream.NONE:
                return original_reply(request_id, stream=stream, **kwargs)
            request = peer.requests[-1]
            command = request.text(2), request.bytes(4)
            if command == zone.get_status("front_left"):
                peer.code = 14
                original_reply(request_id, error=b"private detail AA:BB:CC:DD:EE:FF")
                peer.code = 0
            else:
                original_reply(request_id, body=responses[command])

        peer.reply = replay
        return peer

    connection = ReadOnlyConnection(connect)
    report, failed = await observe(connection, address="AA:BB:CC:DD:EE:FF", seconds=0)
    assert not failed and not connection.connected
    assert not factory.peers[0].is_connected
    trace = report["diagnostic_snapshot"]["probe"]["request_trace"]
    assert trace["total"] == len(factory.peers[0].requests)
    rows = trace["requests"]
    errors = [row for row in rows if row["outcome"] == "error"]
    assert len(errors) == 2  # Initial status and final refresh.
    assert all(row["zone_uid"] == "front_left" and row["response_code"] == 14 for row in errors)
    assert all(row["operation"] == "stream_stop" and row["stream"] == "STOP"
               for row in rows[-3:])
    assert "private detail" not in json.dumps(report)
    assert "AA:BB:CC:DD:EE:FF" not in json.dumps(report)
