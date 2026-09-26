"""Attribute real response errors to their source without retaining private data."""

import asyncio
import json

import pytest
from test_transport import connection as connection

from custom_components.bora.ble.transport import BoraError, ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream, blob, frame, uint

SET_PATH = "/bora.generic.extractor.v1.ExtractorService/SetExtractorMode"
READ_PATH = "/bora.generic.extractor.v1.ExtractorService/GetExtractorStatus"
STREAM_PATH = "/bora.generic.extractor.v1.ExtractorService/StreamExtractorStatusUpdates"


def assert_context(connection, error, request_id, path, code, stream):
    assert error.request_id == request_id
    assert error.path == path
    assert error.code == code
    assert error.stream == stream
    assert connection.last_rpc_error == {
        "request_id": request_id, "path": path, "code": code, "stream": stream.name,
    }


def assert_clean(connection):
    assert not connection._pending
    assert not connection._request_paths
    assert not connection._receivers
    assert not connection._error_receivers


def test_rpc_error_context_is_optional_and_exception_text_remains_private_safe():
    legacy = RpcError(12, b"PRIVATE_ERROR")
    assert legacy.request_id is legacy.path is legacy.stream is None
    contextual = RpcError(
        12, b"PRIVATE_ERROR", request_id=17, path="/PRIVATE_PATH", stream=Stream.NONE
    )
    assert contextual.error == b"PRIVATE_ERROR"
    assert str(contextual) == str(legacy) == "BORA returned response code 12"
    assert "PRIVATE" not in repr(contextual)


@pytest.mark.parametrize("failed_path", [SET_PATH, READ_PATH], ids=["setter", "readback"])
async def test_setter_and_following_readback_failure_have_distinct_sources(connection, failed_path):
    conn, peer, _ = connection
    if failed_path == READ_PATH:
        await conn.rpc(SET_PATH, b"\x0a\x02\x10\x01")
        assert conn.last_rpc_error is None
    peer.code = 12
    callbacks = []

    def failed(error):
        assert not conn._pending[error.request_id].done()
        callbacks.append(error)
        assert conn.last_rpc_error["path"] == failed_path

    with pytest.raises(RpcError) as raised:
        await conn.rpc(failed_path, failed=failed)
    request_id = peer.requests[-1].uint(3)
    assert_context(conn, raised.value, request_id, failed_path, 12, Stream.NONE)
    assert callbacks == [raised.value]
    assert len(peer.requests) == (2 if failed_path == READ_PATH else 1)
    assert_clean(conn)
    copied = conn.last_rpc_error
    copied["path"] = "changed"
    assert conn.last_rpc_error["path"] == failed_path


async def test_stream_start_error_keeps_source_through_automatic_disconnect(connection):
    conn, peer, _ = connection
    peer.code = 12
    with pytest.raises(RpcError) as raised:
        await conn.subscribe(STREAM_PATH, lambda _: None)
    assert_context(conn, raised.value, 1, STREAM_PATH, 12, Stream.START)
    assert not conn.connected and conn.subscription_count == 0
    assert_clean(conn)


async def test_stream_stop_error_keeps_the_subscription_path_and_id(connection):
    conn, peer, _ = connection
    stream_id = await conn.subscribe(STREAM_PATH, lambda _: None)
    peer.code = 7
    with pytest.raises(RpcError) as raised:
        await conn.unsubscribe(stream_id)
    assert_context(conn, raised.value, stream_id, STREAM_PATH, 7, Stream.STOP)
    assert conn.connected and conn.subscription_count == 0
    assert_clean(conn)
    peer.code = 14
    peer.reply(stream_id, stream=Stream.STOP)
    assert conn.last_rpc_error["code"] == 7  # This subscription is no longer active.


@pytest.mark.parametrize("stream", [Stream.NONE, Stream.CONTINUE, Stream.STOP])
async def test_async_stream_error_does_not_become_a_waiting_unary_error(connection, stream):
    conn, peer, _ = connection
    stream_id = await conn.subscribe(STREAM_PATH, lambda _: None)
    peer.respond = False
    callbacks = []
    waiting = []
    for path in (SET_PATH, READ_PATH):
        peer.request_seen.clear()
        waiting.append(asyncio.create_task(conn.rpc(path, failed=callbacks.append)))
        await peer.request_seen.wait()
    peer.code = 14
    peer.reply(stream_id, stream=stream, error=b"PRIVATE_ERROR_AND_IDENTIFIER")
    failures = []
    for task in waiting:
        with pytest.raises(RpcError) as raised:
            await task
        failures.append(raised.value)
        assert_context(conn, raised.value, stream_id, STREAM_PATH, 14, stream)
    assert failures[0] is failures[1]
    assert not callbacks  # No unary error response was received for those RPCs.
    assert not conn.connected and conn.subscription_count == 0
    assert_clean(conn)
    assert "PRIVATE" not in json.dumps(conn.last_rpc_error)
    assert "error" not in conn.last_rpc_error


@pytest.mark.parametrize("ending", ["success", "timeout", "cancel"])
async def test_late_and_unrelated_errors_do_not_replace_last_response_error(connection, ending):
    conn, peer, _ = connection
    peer.code = 12
    with pytest.raises(RpcError):
        await conn.rpc(SET_PATH)
    original = conn.last_rpc_error
    peer.code = 0
    peer.respond = False
    peer.request_seen.clear()
    waiting = asyncio.create_task(conn.rpc(READ_PATH))
    await peer.request_seen.wait()
    request_id = peer.requests[-1].uint(3)
    if ending == "success":
        # The late error arrives before the successful waiter's finally runs.
        peer.notifications(None, bytearray(
            frame(uint(3, request_id) + blob(4, b"valid"))
            + frame(uint(3, request_id) + uint(2, 14))
        ))
        assert await waiting == b"valid"
    elif ending == "timeout":
        with pytest.raises(RequestTimeout):
            await waiting
    else:
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
    peer.code = 7
    peer.reply(request_id)
    peer.reply(request_id + 100)
    assert conn.last_rpc_error == original
    assert_clean(conn)


@pytest.mark.parametrize("failure", ["disconnect", "protocol_error"])
async def test_non_rpc_failures_clean_paths_without_fabricating_rpc_context(connection, failure):
    conn, peer, _ = connection
    peer.respond = False
    waiting = asyncio.create_task(
        conn.rpc(READ_PATH, received=lambda _: None, failed=lambda _: None)
    )
    await peer.request_seen.wait()
    if failure == "disconnect":
        await peer.disconnect()
    else:
        peer.notifications(None, bytearray(b"\x7ebad!\x7c"))
    assert_clean(conn)
    with pytest.raises(BoraError):
        await waiting
    assert conn.last_rpc_error is None


async def test_new_connection_resets_context_and_ignores_old_generation_errors(connection):
    conn, old, factory = connection
    old.code = 12
    with pytest.raises(RpcError):
        await conn.rpc(SET_PATH)
    original = conn.last_rpc_error
    await conn.connect()  # Still the same connection.
    assert conn.last_rpc_error == original
    await conn.disconnect()
    assert conn.last_rpc_error == original
    await conn.connect()
    assert conn.last_rpc_error is None
    new = factory.peers[-1]
    new.respond = False
    waiting = asyncio.create_task(conn.rpc(READ_PATH))
    await new.request_seen.wait()
    request_id = new.requests[-1].uint(3)
    old.reply(request_id)
    assert not waiting.done() and conn.last_rpc_error is None
    new.code = 7
    new.reply(request_id)
    with pytest.raises(RpcError) as raised:
        await waiting
    assert_context(conn, raised.value, request_id, READ_PATH, 7, Stream.NONE)


async def test_old_waiter_cannot_clear_reused_id_metadata_after_connection_failure(connection):
    conn, _, factory = connection
    old_send_started = asyncio.Event()
    release_old_send = asyncio.Event()
    new_send_started = asyncio.Event()
    sends = 0

    async def delayed_send(_packet):
        nonlocal sends
        sends += 1
        if sends == 1:
            old_send_started.set()
            await release_old_send.wait()
        else:
            new_send_started.set()

    conn._send = delayed_send
    old_waiter = asyncio.create_task(conn.rpc(SET_PATH))
    await old_send_started.wait()
    conn._fail(ConnectionLost("Simulated connection failure"))
    await conn.connect()
    conn._counter = 0  # Exercise reuse without sending billions of requests.
    callbacks = []
    new_waiter = asyncio.create_task(conn.rpc(READ_PATH, failed=callbacks.append))
    await new_send_started.wait()
    release_old_send.set()
    with pytest.raises(ConnectionLost):
        await old_waiter
    assert conn._request_paths == {1: READ_PATH}
    peer = factory.peers[-1]
    peer.code = 12
    peer.reply(1)
    with pytest.raises(RpcError) as raised:
        await new_waiter
    assert_context(conn, raised.value, 1, READ_PATH, 12, Stream.NONE)
    assert callbacks == [raised.value]
    assert_clean(conn)
