"""Probe cleanup with a fake device: no discovery, adapter or appliance I/O."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from bleak.exc import BleakError

from custom_components.bora import config_flow
from custom_components.bora.ble.transport import ConnectionLost, PairingRequired
from custom_components.bora.ble.wire import ProtocolError

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def probe_peer():
    connection = SimpleNamespace(disconnect=AsyncMock())
    device = SimpleNamespace(
        initialize=AsyncMock(), information={"product_name": "X PURE", "cm_sw_version_no": "3.0.9"}
    )
    with (
        patch.object(config_flow, "create_connection", return_value=connection) as create,
        patch("custom_components.bora.ble.client.BoraDevice", return_value=device) as device_class,
    ):
        yield connection, device, create, device_class


async def test_successful_probe_pairs_without_subscriptions_and_disconnects(hass, probe_peer):
    connection, device, create, device_class = probe_peer
    info = await config_flow.async_probe(hass, ADDRESS)
    assert info == device.information
    create.assert_called_once_with(hass, ADDRESS)
    device_class.assert_called_once_with(connection)
    device.initialize.assert_awaited_once_with(pair=True, subscribe=False)
    connection.disconnect.assert_awaited_once_with()


@pytest.mark.parametrize(
    "failure",
    [
        PairingRequired(),
        ConnectionLost(),
        BleakError("adapter unavailable"),
        ProtocolError("bad descriptor"),
        RuntimeError("unexpected initialization failure"),
    ],
)
async def test_failed_probe_disconnects_and_preserves_error(hass, probe_peer, failure):
    connection, device, _, _ = probe_peer
    device.initialize.side_effect = failure
    with pytest.raises(type(failure)) as raised:
        await config_flow.async_probe(hass, ADDRESS)
    assert raised.value is failure
    device.initialize.assert_awaited_once_with(pair=True, subscribe=False)
    connection.disconnect.assert_awaited_once_with()


async def test_probe_timeout_cancels_initialization_and_disconnects(hass, probe_peer, monkeypatch):
    connection, device, _, _ = probe_peer
    cancelled = asyncio.Event()

    async def blocked_initialize(**kwargs):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    device.initialize.side_effect = blocked_initialize
    timeouts = []

    def immediate_timeout(seconds):
        timeouts.append(seconds)
        return asyncio.timeout(0)

    # Shorten only the probe's timeout; keep real cancellation and cleanup behavior.
    monkeypatch.setattr(config_flow, "asyncio", SimpleNamespace(timeout=immediate_timeout))
    with pytest.raises(TimeoutError):
        await config_flow.async_probe(hass, ADDRESS)
    assert timeouts == [60]
    assert cancelled.is_set()
    connection.disconnect.assert_awaited_once_with()


async def test_cancelled_probe_disconnects_and_propagates_cancellation(hass, probe_peer):
    connection, device, _, _ = probe_peer
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def blocked_initialize(**kwargs):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    device.initialize.side_effect = blocked_initialize
    task = asyncio.create_task(config_flow.async_probe(hass, ADDRESS))
    await started.wait()
    connection.disconnect.assert_not_awaited()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    connection.disconnect.assert_awaited_once_with()
