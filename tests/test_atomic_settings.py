"""Whole-group writes must preserve concurrent toggles and known settings."""

import asyncio

import pytest
from test_client import Connection

from custom_components.bora.ble import cooktop
from custom_components.bora.ble.client import SIMPLE_FUNCTION_FIELDS, BoraDevice, UnsupportedValue
from custom_components.bora.ble.transport import ConnectionLost
from custom_components.bora.ble.wire import Message, blob, uint


class SimpleConnection(Connection):
    def __init__(self):
        super().__init__()
        self.set_group(b"".join(uint(i, 0) for i in range(1, 6)))

    def set_group(self, group):
        self.responses[cooktop.get_status()] = blob(1, blob(5, blob(6, blob(2, group))))

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        if path.endswith("/SetSpecificCooktopSetting"):
            self.requests.append((path, body))
            # Force competing callers to wait while the first write is in flight.
            await asyncio.sleep(0)
            self.set_group(Message(body).message(1).message(7).bytes(1))
            return b""
        return await super().rpc(path, body, received=received, failed=failed)


async def test_concurrent_toggles_merge_after_previous_readback():
    connection = SimpleConnection()
    appliance = BoraDevice(connection)
    await appliance.initialize()
    await asyncio.gather(
        appliance.set_simple_function("pause_disabled", False),
        appliance.set_simple_function("timer_disabled", False),
    )
    writes = [
        Message(body).message(1).message(7).message(1)
        for path, body in connection.requests
        if path.endswith("/SetSpecificCooktopSetting")
    ]
    assert len(writes) == 2
    assert writes[0].boolean(2) and not writes[0].boolean(4)
    assert writes[1].boolean(2) and writes[1].boolean(4)
    status = appliance.snapshot["cooktop"]["cooktop_settings"]["pure"]
    assert status["super_simple_mode"]["disabled_functions"] == {
        field: field in {"pause_disabled", "timer_disabled"} for field in SIMPLE_FUNCTION_FIELDS
    }
    await appliance.close()


async def test_partial_group_or_unknown_snapshot_never_writes():
    connection = SimpleConnection()
    appliance = BoraDevice(connection)
    await appliance.initialize()
    before = len(connection.requests)
    with pytest.raises(UnsupportedValue):
        await appliance.execute(
            (cooktop.PREFIX + "SetSpecificCooktopSetting", blob(1, blob(7, blob(1, uint(2, 1)))))
        )
    connection.responses[cooktop.get_status()] = blob(1, blob(5, b""))
    await appliance.refresh()
    after_reads = len(connection.requests)
    assert after_reads > before
    with pytest.raises(UnsupportedValue):
        await appliance.set_simple_function("pause_disabled", False)
    assert len(connection.requests) == after_reads
    await appliance.close()


async def test_diagnostics_do_not_reconnect_or_queue():
    appliance = BoraDevice(Connection())
    with pytest.raises(ConnectionLost):
        await appliance.collect_diagnostics()
    assert appliance.connection.connect_count == 0
    assert appliance.diagnostic_snapshot == {}
