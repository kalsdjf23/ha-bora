"""Exercise asynchronous failures and stream/unary multiplexing without BLE."""

import asyncio

import pytest

from custom_components.bora.ble.transport import (
    BOND_UUID,
    RESPONSE_UUID,
    WRITE_UUID,
    BoraError,
    BrpcConnection,
    ConnectionLost,
    PairingRequired,
    RequestTimeout,
    RpcError,
)
from custom_components.bora.ble.wire import FrameDecoder, Message, Stream, blob, frame, uint


class Peer:
    def __init__(self, disconnected, *, bond=1):
        self.is_connected = True
        self.on_disconnect = disconnected
        self.bond = bond
        self.notifications = None
        self.decoder = FrameDecoder()
        self.requests = []
        self.request_seen = asyncio.Event()
        self.chunks = []
        self.respond = True
        self.paired = 0
        self.code = 0
        self.write_barrier = None

    async def read_gatt_char(self, uuid):
        return bytearray([self.bond]) if uuid == BOND_UUID else bytearray(b"\x00")

    async def pair(self):
        self.paired += 1
        self.bond = 1

    async def start_notify(self, uuid, callback):
        assert uuid == RESPONSE_UUID
        self.notifications = callback

    async def write_gatt_char(self, uuid, data, response):
        assert uuid == WRITE_UUID and response
        assert len(data) <= 20
        if self.write_barrier:
            await self.write_barrier.wait()
        assert self.is_connected
        self.chunks.append(data)
        for payload in self.decoder.feed(data):
            message = Message(payload)
            self.requests.append(message)
            self.request_seen.set()
            if not self.respond:
                continue
            if message.uint(6) == Stream.STOP:
                self.reply(message.uint(3), stream=Stream.STOP)
            elif "Stream" in message.text(2):
                self.reply(message.uint(3), stream=Stream.START)
            else:
                self.reply(message.uint(3), body=message.bytes(4) or b"fixture")
        await asyncio.sleep(0)

    def reply(self, request_id, *, stream=Stream.NONE, body=None, error=None):
        payload = uint(3, request_id) + uint(2, self.code)
        if stream:
            payload += uint(7, stream)
        if body is not None:
            payload += blob(4, body)
        if error is not None:
            payload += blob(5, error)
        packet = frame(payload)
        # Deliberately fragment every reply across notifications.
        for offset in range(0, len(packet), 7):
            self.notifications(None, bytearray(packet[offset : offset + 7]))

    async def disconnect(self):
        self.is_connected = False
        self.on_disconnect(self)


class Factory:
    def __init__(self, bond=1):
        self.peers = []
        self.bond = bond

    async def __call__(self, callback):
        peer = Peer(callback, bond=self.bond)
        self.peers.append(peer)
        return peer


@pytest.fixture
async def connection():
    factory = Factory()
    connection = BrpcConnection(factory, timeout=0.1)
    await connection.connect()
    yield connection, factory.peers[0], factory
    await connection.disconnect()


async def test_stream_snapshot_and_stop_keep_the_original_id(connection):
    conn, peer, _ = connection
    seen = []
    stream_id = await conn.subscribe("/fixture/StreamStatus", seen.append)
    assert await conn.rpc("/fixture/GetStatus") == b"fixture"
    peer.reply(stream_id, stream=Stream.CONTINUE, body=b"changed")
    assert seen == [b"changed"]
    await conn.unsubscribe(stream_id)
    assert [m.uint(3) for m in peer.requests] == [1, 2, 1]
    assert peer.requests[-1].uint(6) == Stream.STOP
    assert conn.subscription_count == 0


async def test_concurrent_requests_do_not_interleave_att_frames(connection):
    conn, peer, _ = connection
    bodies = [bytes([index]) * 64 for index in range(1, 5)]
    result = await asyncio.gather(*(conn.rpc("/fixture/Echo", body) for body in bodies))
    assert result == bodies
    assert len(peer.requests) == 4
    assert len({m.uint(3) for m in peer.requests}) == 4


async def test_timeout_is_not_replayed_and_late_response_does_not_satisfy_new_rpc(connection):
    conn, peer, _ = connection
    peer.respond = False
    with pytest.raises(RequestTimeout):
        await conn.rpc("/fixture/SetSomething", b"command")
    assert len(peer.requests) == 1
    peer.reply(1, body=b"late old value")
    peer.respond = True
    assert await conn.rpc("/fixture/GetStatus") == b"fixture"
    assert len(peer.requests) == 2


async def test_disconnect_fails_waiters_and_reconnect_never_replays_controls(connection):
    conn, peer, factory = connection
    peer.respond = False
    pending = asyncio.create_task(conn.rpc("/fixture/SetSomething", b"command"))
    await peer.request_seen.wait()
    await peer.disconnect()
    with pytest.raises(ConnectionLost):
        await pending
    await conn.connect()
    assert len(factory.peers) == 2
    assert factory.peers[-1].requests == []
    assert await conn.rpc("/fixture/GetStatus") == b"fixture"
    assert factory.peers[-1].requests[0].text(2) == "/fixture/GetStatus"


async def test_rpc_error_without_successful_state(connection):
    conn, peer, _ = connection
    peer.code = 7
    with pytest.raises(RpcError) as err:
        await conn.rpc("/fixture/GetStatus")
    assert err.value.code == 7


async def test_bonding_is_only_attempted_explicitly():
    factory = Factory(bond=0)
    conn = BrpcConnection(factory)
    with pytest.raises(PairingRequired):
        await conn.connect()
    assert factory.peers[0].paired == 0 and not factory.peers[0].is_connected
    await conn.connect(pair=True)
    assert factory.peers[-1].paired == 1 and conn.bond_state == 1
    await conn.disconnect()


async def test_corrupt_frame_marks_connection_unavailable_and_fails_pending(connection):
    conn, peer, _ = connection
    peer.respond = False
    pending = asyncio.create_task(conn.rpc("/fixture/GetStatus"))
    await peer.request_seen.wait()
    peer.notifications(None, bytearray(b"\x7ebad!\x7c"))
    with pytest.raises(BoraError):
        await pending
    assert not conn.connected and conn.last_protocol_error


async def test_cancelled_request_cleans_up_pending_future(connection):
    conn, peer, _ = connection
    peer.respond = False
    pending = asyncio.create_task(conn.rpc("/fixture/GetStatus"))
    await peer.request_seen.wait()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    peer.respond = True
    assert await conn.rpc("/fixture/GetStatus") == b"fixture"
    assert not conn._pending


async def test_old_connection_notifications_are_ignored_after_reconnect(connection):
    conn, old, factory = connection
    await conn.disconnect()
    await conn.connect()
    new = factory.peers[-1]
    new.respond = False
    pending = asyncio.create_task(conn.rpc("/fixture/GetStatus"))
    await new.request_seen.wait()
    new_id = new.requests[-1].uint(3)
    old.reply(new_id, body=b"stale")
    assert not pending.done()
    new.reply(new_id, body=b"fresh")
    assert await pending == b"fresh"


async def test_disconnect_while_connector_is_pending_closes_late_client():
    entered = asyncio.Event()
    release = asyncio.Event()
    factory = Factory()

    async def delayed_connector(callback):
        entered.set()
        await release.wait()
        return await factory(callback)

    conn = BrpcConnection(delayed_connector)
    connecting = asyncio.create_task(conn.connect())
    await entered.wait()
    await conn.disconnect()
    release.set()
    with pytest.raises(ConnectionLost):
        await connecting
    assert not conn.connected
    assert not factory.peers[0].is_connected


async def test_unexpected_stream_stop_invalidates_connection(connection):
    conn, peer, _ = connection
    stream_id = await conn.subscribe("/fixture/StreamStatus", lambda _: None)
    peer.reply(stream_id, stream=Stream.STOP)
    assert not conn.connected and conn.subscription_count == 0


async def test_unary_commit_and_stream_are_dispatched_in_wire_order(connection):
    conn, peer, _ = connection
    received = []
    stream_id = await conn.subscribe(
        "/fixture/StreamStatus", lambda body: received.append(("stream", body))
    )
    peer.respond = False
    peer.request_seen.clear()
    waiting = asyncio.create_task(
        conn.rpc("/fixture/GetStatus", received=lambda body: received.append(("unary", body)))
    )
    await peer.request_seen.wait()
    query_id = peer.requests[-1].uint(3)
    packet = frame(uint(3, query_id) + blob(4, b"old"))
    packet += frame(uint(3, stream_id) + uint(7, Stream.CONTINUE) + blob(4, b"new"))
    peer.notifications(None, bytearray(packet))
    assert received == [("unary", b"old"), ("stream", b"new")]
    assert await waiting == b"old"
    peer.respond = True
