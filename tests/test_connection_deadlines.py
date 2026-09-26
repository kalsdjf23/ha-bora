"""Backend stalls cannot indefinitely block setup or detach."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from test_transport import Factory

from custom_components.bora.ble.transport import BrpcConnection


@pytest.mark.parametrize("stalled_method", ["read_gatt_char", "pair", "start_notify"])
async def test_backend_setup_stall_expires_and_disconnects(stalled_method):
    factory = Factory(bond=0 if stalled_method == "pair" else 1)

    async def stalled(*args):
        await asyncio.Event().wait()

    async def connect(callback):
        peer = await factory(callback)
        setattr(peer, stalled_method, stalled)
        return peer

    conn = BrpcConnection(connect, connect_timeout=0.01)
    with pytest.raises(TimeoutError):
        await conn.connect(pair=stalled_method == "pair")
    assert not conn.connected
    assert not factory.peers[0].is_connected
    assert factory.peers[0].requests == []
    assert not conn._pending


async def test_stalled_disconnect_invalidates_session_and_ignores_late_updates():
    factory = Factory()
    conn = BrpcConnection(factory, disconnect_timeout=0.01)
    await conn.connect()
    old = factory.peers[-1]
    cancelled = asyncio.Event()

    async def stalled():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    old.disconnect = AsyncMock(side_effect=stalled)
    await conn.disconnect()
    assert cancelled.is_set()
    assert not conn.connected
    assert conn._generation is None
    # Local invalidation cannot promise the stalled backend disconnected the
    # radio. It does ensure its callbacks cannot modify a new connection.
    await conn.connect()
    old.reply(1, body=b"late data")
    assert conn.connected
    assert await conn.rpc("/fixture/GetStatus") == b"fixture"
    await conn.disconnect()
