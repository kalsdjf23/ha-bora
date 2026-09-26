"""State initialization and command validation against recorded responses."""

import json
from pathlib import Path

import pytest

from custom_components.bora.ble import cooktop, extractor, identify, zone
from custom_components.bora.ble.client import BoraDevice, UnsupportedValue
from custom_components.bora.ble.transport import ConnectionLost, RpcError
from custom_components.bora.ble.wire import (
    FrameDecoder,
    Message,
    Response,
    Stream,
    blob,
    string,
    uint,
)


def recorded_responses():
    result = {}
    sessions = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())[
        "sessions"
    ]
    for session in sessions:
        methods = {}
        decoder = FrameDecoder()
        for event in session["events"]:
            if event["event"] == "request":
                payload = FrameDecoder().feed(bytes.fromhex(event["hex"]))[0]
                message = Message(payload)
                methods[message.uint(3)] = (message.text(2), message.bytes(4))
            else:
                for payload in decoder.feed(bytes.fromhex(event["hex"])):
                    reply = Response.decode(payload)
                    if reply.stream == Stream.NONE and reply.body is not None:
                        result[methods[reply.request_id]] = reply.body
    result[identify.get_information()] = uint(1, 2) + string(8, "fixture-fw")
    return result


class Connection:
    def __init__(self):
        self.connected = False
        self.responses = recorded_responses()
        self.requests = []
        self.streams = {}
        self.unsupported = set()
        self.connect_count = 0

    async def connect(self, **kwargs):
        if not self.connected:
            self.connect_count += 1
        self.connected = True

    async def disconnect(self):
        self.connected = False
        self.streams.clear()

    async def subscribe(self, path, callback):
        if path in self.unsupported:
            await self.disconnect()
            raise RpcError(12)
        self.streams[path] = callback
        return len(self.streams)

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        assert self.connected
        self.requests.append((path, body))
        if path.endswith("SetExtractorMode"):
            mode = Message(body).bytes(1)
            old = Message(self.responses[extractor.get_status()])
            settings = Message(old.bytes(1))
            self.responses[extractor.get_status()] = blob(
                1, blob(2, mode) + blob(3, settings.bytes(3))
            )
            return b""  # acknowledgement alone must not be used as a new status
        response = self.responses[(path, body)]
        if isinstance(response, BaseException):
            if isinstance(response, RpcError) and failed:
                failed(response)
            raise response
        if received:
            received(response)
        return response


@pytest.fixture
async def device():
    connection = Connection()
    device = BoraDevice(connection)
    await device.initialize()
    yield device, connection
    await device.close()


async def test_reads_explicit_snapshots_and_four_zones_without_controls(device):
    appliance, connection = device
    assert len(appliance.zone_uids) == 4
    assert len(appliance.snapshot["zones"]) == 4
    assert (
        appliance.snapshot["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 0
    )
    assert len(connection.streams) == 3
    assert all("/Get" in path for path, _ in connection.requests)


async def test_unimplemented_stream_uses_reads_and_remaining_streams():
    connection = Connection()
    connection.unsupported.add(zone.STREAM_PATH)
    appliance = BoraDevice(connection)
    await appliance.initialize()
    assert connection.connect_count == 2
    assert zone.STREAM_PATH not in connection.streams
    assert len(appliance.snapshot["zones"]) == 4
    await appliance.close()


async def test_stream_and_reads_preserve_unknown_and_defaults(device):
    appliance, connection = device
    connection.streams[extractor.STREAM_PATH](blob(1, blob(2, blob(1, b""))))
    mode = appliance.snapshot["extractor"]["extractor_settings"]["extractor_mode"]
    assert mode["mode"] == "auto"
    assert mode.get("power_level") is None
    connection.streams[cooktop.STREAM_PATH](b"")
    assert appliance.snapshot["cooktop"]["cooktop_settings"] is None


async def test_validate_caps_and_confirm_control_with_readback(device):
    appliance, connection = device
    before = len(connection.requests)
    snapshot = await appliance.execute(extractor.set_power_level(3))
    assert snapshot["extractor"]["extractor_settings"]["extractor_mode"]["power_level"] == 3
    assert connection.requests[before] == extractor.set_power_level(3)
    assert all("/Get" in path for path, _ in connection.requests[before + 1 :])
    with pytest.raises(UnsupportedValue):
        await appliance.execute(extractor.set_power_level(10))
    with pytest.raises(UnsupportedValue):
        await appliance.execute(extractor.set_after_run_duration(4))
    with pytest.raises(UnsupportedValue):
        await appliance.execute(zone.set_power("unknown", 1))
    with pytest.raises(UnsupportedValue):
        await appliance.execute(zone.set_power("front_left", 11))


async def test_device_never_connects_to_deliver_queued_control(device):
    appliance, connection = device
    await connection.disconnect()
    calls = len(connection.requests)
    with pytest.raises(ConnectionLost):
        await appliance.execute(extractor.set_power_level(3))
    assert len(connection.requests) == calls
    assert not connection.connected
    await appliance.refresh()
    assert connection.connected
    assert all("/Get" in path for path, _ in connection.requests[calls:])


async def test_no_destructive_or_unverified_generic_action(device):
    appliance, _ = device
    for command in (
        cooktop.set_filter_unit(),
        cooktop.set_led_test(True),
        cooktop.restart_connectivity_module(),
        zone.set_bridged("front_left", "back_left"),
        zone.start_or_modify_csf(
            "front_left", {"csf_id": 1, "csf_type": 1, "csf_timer_duration": 30000}
        ),
        ("/bora.generic.debug.v1.DebugService/InvokeFactoryReset", b""),
    ):
        with pytest.raises(UnsupportedValue):
            appliance.validate_command(command)


async def test_timer_ranges_are_checked_without_assuming_units(device):
    appliance, _ = device
    appliance.validate_command(zone.set_timer("front_left", 1000))
    with pytest.raises(UnsupportedValue):
        appliance.validate_command(zone.set_timer("front_left", 1))
    with pytest.raises(UnsupportedValue):
        appliance.validate_command(extractor.set_egg_timer(0xFFFFFFFF))


@pytest.mark.parametrize("variable_support", [False, None])
@pytest.mark.parametrize("mode", [1, 2, 3])
async def test_unverified_fixed_retention_is_rejected_before_io(device, variable_support, mode):
    appliance, connection = device
    descriptor = appliance.descriptor["zone_descriptor"]
    assert 3 in descriptor["zone_mode_types"]
    if variable_support is None:
        descriptor.pop("variable_heat_retention_support")
    else:
        descriptor["variable_heat_retention_support"] = variable_support
    before_requests = list(connection.requests)
    before_snapshot = appliance.snapshot

    # HEAT_RETENTION alone does not prove that fixed mode 2 is supported.
    with pytest.raises(UnsupportedValue):
        await appliance.execute(zone.set_keep_warm("front_left", mode))
    assert connection.requests == before_requests
    assert appliance.snapshot == before_snapshot


@pytest.mark.parametrize("mode", [1, 2, 3])
async def test_advertised_variable_retention_keeps_known_modes(device, mode):
    appliance, connection = device
    descriptor = appliance.descriptor["zone_descriptor"]
    assert 3 in descriptor["zone_mode_types"]
    assert descriptor["variable_heat_retention_support"] is True
    before_requests = list(connection.requests)
    appliance.validate_command(zone.set_keep_warm("front_left", mode))
    assert connection.requests == before_requests
