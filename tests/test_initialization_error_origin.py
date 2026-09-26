"""Initialization fallback requires an error from the attempted RPC."""

import pytest
from test_client import Connection, recorded_responses
from test_transport import Factory, Peer

from custom_components.bora.ble import cooktop, extractor, identify, zone
from custom_components.bora.ble.client import BoraDevice
from custom_components.bora.ble.transport import BrpcConnection, RpcError
from custom_components.bora.ble.wire import Stream


class InitializationFactory(Factory):
    """Replay recorded reads through real framing and inject selected replies."""

    def __init__(self):
        super().__init__()
        self.responses = recorded_responses()
        self.intercept = lambda *_: False

    async def __call__(self, callback):
        peer = await super().__call__(callback)
        reply = peer.reply

        def recorded_reply(request_id, *, stream=Stream.NONE, **kwargs):
            request = peer.requests[-1]
            if self.intercept(peer, reply, request, stream):
                return
            if stream == Stream.NONE:
                kwargs["body"] = self.responses[(request.text(2), request.bytes(4))]
            reply(request_id, stream=stream, **kwargs)

        peer.reply = recorded_reply
        return peer


@pytest.fixture
async def initializing_device():
    factory = InitializationFactory()
    connection = BrpcConnection(factory, timeout=0.1)
    device = BoraDevice(connection)
    yield device, connection, factory
    await device.close()


@pytest.mark.parametrize("error_stream", [Stream.NONE, Stream.CONTINUE, Stream.STOP])
async def test_established_stream_error_does_not_disable_pending_stream(
    initializing_device, error_stream
):
    device, connection, factory = initializing_device
    origin_id = None

    def interrupt(peer, reply, request, stream):
        nonlocal origin_id
        if len(factory.peers) == 1 and request.text(2) == cooktop.STREAM_PATH:
            origin_id = next(
                item.uint(3) for item in peer.requests if item.text(2) == extractor.STREAM_PATH
            )
            peer.code = 12
            reply(origin_id, stream=error_stream)
            peer.code = 0
            return True
        return False

    factory.intercept = interrupt
    with pytest.raises(RpcError) as raised:
        await device.initialize()
    assert raised.value.request_id == origin_id
    assert raised.value.path == extractor.STREAM_PATH
    assert raised.value.stream == error_stream
    assert not device._unsupported_streams
    assert not connection.connected
    assert len(factory.peers) == 1
    # A later explicit retry keeps every valid stream available; the failed
    # attempt did not permanently teach the client that the cooktop lacks one.
    factory.intercept = lambda *_: False
    await device.initialize()
    assert len(factory.peers) == 2 and connection.subscription_count == 3
    assert not device._unsupported_streams
    assert all(
        "/Get" in request.text(2) or "/Stream" in request.text(2)
        for peer in factory.peers for request in peer.requests
    )


@pytest.mark.parametrize("error_stream", [Stream.NONE, Stream.START])
async def test_direct_unsupported_streams_have_bounded_read_only_fallback(
    initializing_device, error_stream
):
    device, connection, factory = initializing_device
    unsupported = {extractor.STREAM_PATH, cooktop.STREAM_PATH, zone.STREAM_PATH}

    def reject_setup(peer, reply, request, stream):
        if request.text(2) in unsupported and stream == Stream.START:
            peer.code = 12
            reply(request.uint(3), stream=error_stream)
            peer.code = 0
            return True
        return False

    factory.intercept = reject_setup
    snapshot = await device.initialize()
    assert len(factory.peers) == 4
    assert device._unsupported_streams == unsupported
    assert connection.connected and connection.subscription_count == 0
    assert len(snapshot["zones"]) == 4
    assert all(
        "/Get" in request.text(2) or "/Stream" in request.text(2)
        for peer in factory.peers for request in peer.requests
    )


@pytest.mark.parametrize("error_stream", [Stream.CONTINUE, Stream.STOP])
async def test_wrong_stream_marker_does_not_prove_setup_is_unsupported(
    initializing_device, error_stream
):
    device, connection, factory = initializing_device

    def reject_setup(peer, reply, request, stream):
        if request.text(2) == extractor.STREAM_PATH and stream == Stream.START:
            peer.code = 12
            reply(request.uint(3), stream=error_stream)
            peer.code = 0
            return True
        return False

    factory.intercept = reject_setup
    with pytest.raises(RpcError) as raised:
        await device.initialize()
    assert raised.value.path == extractor.STREAM_PATH
    assert not device._unsupported_streams
    assert not connection.connected and len(factory.peers) == 1


@pytest.mark.parametrize("error_stream", list(Stream))
async def test_information_unsupported_requires_a_unary_response(
    initializing_device, error_stream
):
    device, connection, factory = initializing_device

    def reject_information(peer, reply, request, stream):
        if request.text(2) == identify.get_information()[0]:
            peer.code = 12
            reply(request.uint(3), stream=error_stream)
            peer.code = 0
            return True
        return False

    factory.intercept = reject_information
    if error_stream == Stream.NONE:
        snapshot = await device.initialize()
        assert device.information == {}
        assert len(snapshot["zones"]) == 4
        assert connection.connected and connection.subscription_count == 3
    else:
        with pytest.raises(RpcError) as raised:
            await device.initialize()
        assert raised.value.path == identify.get_information()[0]
        assert not connection.connected
    assert len(factory.peers) == 1
    assert not device._unsupported_streams


@pytest.mark.parametrize("operation", ["information", "subscribe"])
@pytest.mark.parametrize("missing", ["request_id", "path", "stream", "all"])
async def test_missing_error_context_does_not_prove_method_unsupported(operation, missing):
    connection = Connection()
    device = BoraDevice(connection)
    path = identify.get_information()[0] if operation == "information" else extractor.STREAM_PATH
    context = {
        "request_id": 7, "path": path,
        "stream": Stream.NONE if operation == "information" else Stream.START,
    }
    if missing == "all":
        context.clear()
    else:
        context.pop(missing)
    error = RpcError(12, **context)
    if operation == "information":
        connection.responses[identify.get_information()] = error
    else:
        async def reject_setup(*_args):
            raise error

        connection.subscribe = reject_setup
    try:
        with pytest.raises(RpcError) as raised:
            await device.initialize()
        assert raised.value is error
        assert connection.connect_count == 1
        assert not connection.connected and not device._unsupported_streams
    finally:
        await device.close()


async def test_reinitialize_closes_old_generation_before_rebuilding_subscriptions(
    initializing_device,
):
    device, connection, factory = initializing_device
    await device.initialize()
    old = factory.peers[0]
    old_stream_id = next(
        request.uint(3) for request in old.requests if request.text(2) == extractor.STREAM_PATH
    )
    old_start_count = sum(request.uint(6) != Stream.STOP and "/Stream" in request.text(2)
                          for request in old.requests)
    late_error_sent = False

    def old_stream_error(peer, reply, request, stream):
        nonlocal late_error_sent
        if request.text(2) != extractor.STREAM_PATH or stream != Stream.START:
            return False
        old.code = 12
        Peer.reply(old, old_stream_id, stream=Stream.NONE)
        old.code = 0
        late_error_sent = True
        # If reinitialization reused the old peer, its active stream error
        # would abort this new subscribe and wrongly mark the path unsupported.
        return peer is old

    factory.intercept = old_stream_error
    snapshot = await device.initialize()
    assert len(factory.peers) == 2
    assert not old.is_connected
    assert sum(request.uint(6) == Stream.STOP for request in old.requests) == 3
    assert sum(request.uint(6) != Stream.STOP and "/Stream" in request.text(2)
               for request in old.requests) == old_start_count == 3
    new = factory.peers[-1]
    starts = [request.text(2) for request in new.requests if "/Stream" in request.text(2)]
    assert starts == [extractor.STREAM_PATH, cooktop.STREAM_PATH, zone.STREAM_PATH]
    assert late_error_sent and not device._unsupported_streams
    assert connection.last_rpc_error is None
    assert connection.connected and connection.subscription_count == 3
    assert len(snapshot["zones"]) == 4
    assert all(
        "/Get" in request.text(2) or "/Stream" in request.text(2)
        for peer in factory.peers for request in peer.requests
    )


async def test_initialization_on_disconnected_transport_does_not_close_it_first():
    connection = Connection()
    device = BoraDevice(connection)
    disconnects = 0
    disconnect = connection.disconnect

    async def tracked_disconnect():
        nonlocal disconnects
        disconnects += 1
        await disconnect()

    connection.disconnect = tracked_disconnect
    try:
        await device.initialize()
        assert connection.connect_count == 1
        assert disconnects == 0
    finally:
        await device.close()
