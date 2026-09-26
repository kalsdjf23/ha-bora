"""A receipt acknowledgement must not become an unobserved successful action."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.ble import extractor
from custom_components.bora.ble.client import CONTROL_PATHS, BoraDevice, CommandNotConfirmed
from custom_components.bora.ble.wire import blob, uint
from custom_components.bora.const import CONF_ENABLE_CONTROLS, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator


class AckOnlyConnection(Connection):
    """Peer accepts the request but leaves its state untouched."""

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        if path in CONTROL_PATHS:
            self.requests.append((path, body))
            return b""
        return await super().rpc(path, body, received=received, failed=failed)


@pytest.mark.parametrize("readback", [blob(1, blob(2, uint(2, 0))), b""])
async def test_accepted_but_unobserved_command_fails_without_retry(readback):
    connection = AckOnlyConnection()
    appliance = BoraDevice(connection)
    await appliance.initialize()
    connection.responses[extractor.get_status()] = readback
    start = len(connection.requests)
    try:
        with pytest.raises(CommandNotConfirmed):
            await appliance.execute(extractor.set_power_level(3))
        assert connection.requests[start] == extractor.set_power_level(3)
        assert all("/Get" in path for path, _ in connection.requests[start + 1:])
        assert connection.connected
        assert appliance.snapshot["extractor"] == extractor.decode_status(readback)
    finally:
        await appliance.shutdown()


@pytest.mark.parametrize("readback", [blob(1, blob(2, uint(2, 2))), b""])
async def test_ha_keeps_actual_readback_available_after_unconfirmed_command(hass, readback):
    connection = AckOnlyConnection()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        coordinator = BoraCoordinator(hass, entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    connection.responses[extractor.get_status()] = readback
    try:
        with pytest.raises(HomeAssistantError, match="not yet show the requested state"):
            await coordinator.async_execute(extractor.set_power_level(3))
        assert coordinator.data["extractor"] == extractor.decode_status(readback)
        assert coordinator.last_update_success
        assert connection.connected
        await coordinator.async_refresh()
        assert sum(path in CONTROL_PATHS for path, _ in connection.requests) == 1
        # The state may arrive later; accepting a later stream never retries
        # the command or changes the already reported uncertain outcome.
        late = blob(1, blob(2, uint(2, 3)))
        connection.streams[extractor.STREAM_PATH](late)
        assert coordinator.data["extractor"] == extractor.decode_status(late)
        assert sum(path in CONTROL_PATHS for path, _ in connection.requests) == 1
    finally:
        await coordinator.async_close()
