"""Unary error callbacks preserve arrival order and never outlive requests."""

import asyncio

import pytest
from test_transport import connection as connection

from custom_components.bora.ble.transport import BoraError, ConnectionLost, RequestTimeout, RpcError
from custom_components.bora.ble.wire import ProtocolError, Stream, blob, frame, uint


@pytest.mark.parametrize("error_first", [True, False])
async def test_unary_error_and_stream_commit_in_wire_order(connection, error_first):
    conn, peer, _ = connection
    events = []
    state = {"zone": b"previous"}

    def updated(body):
        state["zone"] = body
        events.append("stream")

    def failed(error):
        assert error.code == 14
        assert not conn._pending[query_id].done()
        state.pop("zone", None)
        events.append("error")

    stream_id = await conn.subscribe("/fixture/StreamStatus", updated)
    peer.respond = False
    peer.request_seen.clear()
    waiting = asyncio.create_task(conn.rpc("/fixture/GetStatus", failed=failed))
    await peer.request_seen.wait()
    query_id = peer.requests[-1].uint(3)
    error = frame(uint(3, query_id) + uint(2, 14))
    update = frame(uint(3, stream_id) + uint(7, Stream.CONTINUE) + blob(4, b"new"))
    peer.notifications(None, bytearray(error + update if error_first else update + error))

    # Both commits happen synchronously, before the waiting coroutine resumes.
    assert events == (["error", "stream"] if error_first else ["stream", "error"])
    assert state == ({"zone": b"new"} if error_first else {})
    with pytest.raises(RpcError, match="14"):
        await waiting
    assert not conn._error_receivers
    assert conn.connected and conn.subscription_count == 1
    peer.respond = True


@pytest.mark.parametrize(
    "outcome", ["success", "rpc_error", "timeout", "cancel", "disconnect", "protocol_error"]
)
async def test_error_callback_cleanup_and_late_error_ignored(connection, outcome):
    conn, peer, _ = connection
    errors = []
    peer.respond = False
    waiting = asyncio.create_task(conn.rpc("/fixture/GetStatus", failed=errors.append))
    await peer.request_seen.wait()
    query_id = peer.requests[-1].uint(3)
    assert query_id in conn._error_receivers

    if outcome == "success":
        peer.reply(query_id, body=b"current")
        assert await waiting == b"current"
    elif outcome == "rpc_error":
        peer.code = 14
        peer.reply(query_id)
        with pytest.raises(RpcError) as raised:
            await waiting
        assert errors == [raised.value]
    elif outcome == "timeout":
        with pytest.raises(RequestTimeout):
            await waiting
    elif outcome == "cancel":
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
    elif outcome == "disconnect":
        await peer.disconnect()
        assert not conn._error_receivers
        with pytest.raises(ConnectionLost):
            await waiting
    else:
        peer.notifications(None, bytearray(b"\x7ebad!\x7c"))
        assert not conn._error_receivers
        with pytest.raises(BoraError):
            await waiting

    assert not conn._pending
    assert not conn._error_receivers
    count = len(errors)
    peer.code = 14
    peer.reply(query_id)
    assert len(errors) == count == (1 if outcome == "rpc_error" else 0)


@pytest.mark.parametrize("stream", [Stream.START, Stream.CONTINUE, Stream.STOP])
async def test_non_unary_error_does_not_call_unary_error_callback(connection, stream):
    conn, peer, _ = connection
    errors = []
    peer.respond = False
    waiting = asyncio.create_task(conn.rpc("/fixture/GetStatus", failed=errors.append))
    await peer.request_seen.wait()
    peer.code = 14
    peer.reply(peer.requests[-1].uint(3), stream=stream)
    with pytest.raises(RpcError):
        await waiting
    assert not errors
    assert not conn._error_receivers


async def test_invalid_error_callback_fails_connection_and_cleans_up(connection):
    conn, peer, _ = connection

    def failed(_error):
        raise ProtocolError("Invalid local error update")

    peer.code = 14
    with pytest.raises(BoraError, match="Invalid BORA protocol response"):
        await conn.rpc("/fixture/GetStatus", failed=failed)
    assert not conn.connected
    assert not conn._pending
    assert not conn._error_receivers
