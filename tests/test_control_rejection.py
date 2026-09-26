"""Direct unsupported setters must not hide otherwise valid monitoring."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_client import Connection

from custom_components.bora.ble import cooktop, extractor, zone
from custom_components.bora.ble.client import CONTROL_PATHS
from custom_components.bora.ble.transport import RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream, blob, uint
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN
from custom_components.bora.coordinator import BoraCoordinator
from custom_components.bora.entity import BoraEntity, extractor_status

FAN_PATH = extractor.set_power_level(1)[0]
SIMPLE_PATH = cooktop.PREFIX + "SetSpecificCooktopSetting"
ASSIST_PATH = zone.SERVICE_PATH + "StartOrModifyCsf"


class RejectingConnection(Connection):
    """Return a chosen error without applying or retrying the rejected RPC."""

    def __init__(self):
        super().__init__()
        self.responses[cooktop.get_status()] = blob(
            1, blob(5, blob(6, blob(2, b"".join(uint(i, 0) for i in range(1, 6)))))
        )
        self.failure_path = None
        self.failure = None
        self.before_failure = None

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        if path == self.failure_path:
            assert self.connected
            self.requests.append((path, body))
            if self.before_failure:
                self.before_failure()
            if isinstance(self.failure, RpcError) and failed:
                failed(self.failure)
            raise self.failure
        return await super().rpc(path, body, received=received, failed=failed)


@pytest.fixture
async def coordinator(hass):
    connection = RejectingConnection()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: True},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bora.coordinator.create_connection", return_value=connection):
        result = BoraCoordinator(hass, entry)
    await result.async_refresh()
    assert result.last_update_success
    yield result, connection
    await result.async_close()


@pytest.mark.parametrize("path", [FAN_PATH, SIMPLE_PATH, ASSIST_PATH])
async def test_direct_unsupported_setter_keeps_status_without_reads_or_replay(coordinator, path):
    result, connection = coordinator
    connection.failure_path = path
    connection.failure = RpcError(12, request_id=12, path=path, stream=Stream.NONE)
    entity = BoraEntity(result, "status", "Status", extractor_status)
    snapshot = result.data
    before = len(connection.requests)

    with pytest.raises(HomeAssistantError, match="does not support this requested action") as err:
        if path == FAN_PATH:
            await result.async_execute(extractor.set_power_level(1))
        elif path == SIMPLE_PATH:
            await result.async_set_simple_function("pause_disabled", False)
        else:
            result.select_assist("front_left", 62176)
            await result.async_start_assist("front_left")

    assert err.value.__cause__ is connection.failure
    assert result.data == snapshot
    assert result.last_update_success and entity.available and connection.connected
    assert result.controls_enabled and result.cooking_enabled
    requests = connection.requests[before:]
    assert requests[-1][0] == path
    assert sum(p in CONTROL_PATHS for p, _ in requests) == 1
    # An Assist has existing safety reads before transmission, never after
    # this rejection. Its separate duplicate-start guard remains unchanged.
    assert all("/Get" in p for p, _ in requests[:-1])
    if path == ASSIST_PATH:
        assert result.device.assist_start_blocked("front_left")

    await result.async_refresh()
    assert result.last_update_success
    assert sum(p in CONTROL_PATHS for p, _ in connection.requests[before:]) == 1


async def test_rejection_preserves_newer_stream_and_does_not_blacklist_controls(coordinator):
    result, connection = coordinator
    connection.failure_path = FAN_PATH
    connection.failure = RpcError(12, request_id=12, path=FAN_PATH, stream=Stream.NONE)
    observed = blob(1, blob(2, uint(2, 2)))
    connection.before_failure = lambda: connection.streams[extractor.STREAM_PATH](observed)

    with pytest.raises(HomeAssistantError, match="does not support this requested action"):
        await result.async_execute(extractor.set_power_level(1))
    assert result.data["extractor"] == extractor.decode_status(observed)
    assert result.last_update_success
    assert sum(p in CONTROL_PATHS for p, _ in connection.requests) == 1

    # A later explicit command is still validated and sent normally. The
    # first error is not treated as evidence that every value is unsupported.
    connection.failure_path = None
    await result.async_execute(extractor.set_power_level(3))
    assert result.data["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 3
    assert sum(p in CONTROL_PATHS for p, _ in connection.requests) == 2


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(RpcError(12), id="unattributed"),
        pytest.param(RpcError(12, path=FAN_PATH, stream=Stream.NONE), id="missing-request-id"),
        pytest.param(RpcError(12, request_id=12, path=FAN_PATH), id="missing-stream-kind"),
        pytest.param(
            RpcError(12, request_id=12, path=extractor.get_status()[0], stream=Stream.NONE),
            id="different-unary-source",
        ),
        pytest.param(
            RpcError(12, request_id=3, path=extractor.STREAM_PATH, stream=Stream.CONTINUE),
            id="asynchronous-stream-error",
        ),
        pytest.param(
            RpcError(12, request_id=12, path=FAN_PATH, stream=Stream.START),
            id="non-unary-even-with-same-path",
        ),
        pytest.param(
            RpcError(14, request_id=12, path=FAN_PATH, stream=Stream.NONE),
            id="different-response-code",
        ),
        pytest.param(RequestTimeout("Reply not received"), id="request-timeout"),
        pytest.param(TimeoutError(), id="operation-timeout"),
    ],
)
async def test_uncertain_or_unrelated_failure_keeps_existing_failure_boundary(coordinator, failure):
    result, connection = coordinator
    connection.failure_path = FAN_PATH
    connection.failure = failure
    with pytest.raises(HomeAssistantError, match="could not confirm this operation"):
        await result.async_execute(extractor.set_power_level(1))
    assert not result.last_update_success
    assert sum(p in CONTROL_PATHS for p, _ in connection.requests) == 1


async def test_unimplemented_readback_after_acknowledged_setter_is_not_a_rejection(coordinator):
    result, connection = coordinator
    path = extractor.get_status()[0]
    connection.failure_path = path
    connection.failure = RpcError(12, request_id=13, path=path, stream=Stream.NONE)
    with pytest.raises(HomeAssistantError, match="could not confirm this operation"):
        await result.async_execute(extractor.set_power_level(1))
    assert not result.last_update_success
    assert connection.requests[-2:] == [extractor.set_power_level(1), extractor.get_status()]


@pytest.mark.parametrize("change", ["disconnect", "status-error", "closed"])
async def test_direct_rejection_cannot_restore_availability_lost_during_rpc(coordinator, change):
    result, connection = coordinator
    connection.failure_path = FAN_PATH
    connection.failure = RpcError(12, request_id=12, path=FAN_PATH, stream=Stream.NONE)

    def make_unavailable():
        if change == "disconnect":
            connection.connected = False
            result._on_disconnect()
        elif change == "status-error":
            result.async_set_update_error(UpdateFailed("Status failed while command was pending"))
        else:
            result._closed = True

    connection.before_failure = make_unavailable
    with pytest.raises(HomeAssistantError, match="could not confirm this operation"):
        await result.async_execute(extractor.set_power_level(1))
    assert not result.last_update_success
    assert sum(p in CONTROL_PATHS for p, _ in connection.requests) == 1


async def test_already_unavailable_coordinator_never_delivers_a_command(coordinator):
    result, connection = coordinator
    result.async_set_update_error(UpdateFailed("No current status"))
    before = list(connection.requests)
    with pytest.raises(HomeAssistantError, match="unavailable; the command was not queued"):
        await result.async_execute(extractor.set_power_level(1))
    assert connection.requests == before
    assert not result.last_update_success
