"""Protocol behavior against recordings and malformed peers."""

import json
import zlib
from pathlib import Path

import pytest

from custom_components.bora.ble.wire import (
    FrameDecoder,
    Message,
    ProtocolError,
    Response,
    Stream,
    blob,
    frame,
    request,
    sint32,
    uint,
)

FIXTURE = Path(__file__).parent / "fixtures" / "x_pure_3_0_9.json"


def test_recorded_frames_and_request_ids():
    count = 0
    for session in json.loads(FIXTURE.read_text())["sessions"]:
        decoder = FrameDecoder()
        ids = set()
        for event in session["events"]:
            if event["event"] == "request":
                decoded = FrameDecoder().feed(bytes.fromhex(event["hex"]))
                message = Message(decoded[0])
                assert message.uint(3) == event["request_id"]
                assert message.text(2).endswith("/" + event["method"])
                assert (
                    request(
                        message.text(2),
                        message.uint(3),
                        message.bytes(4),
                        stop=message.uint(6) == 2,
                    ).hex()
                    == event["hex"]
                )
                ids.add(event["request_id"])
            else:
                for payload in decoder.feed(bytes.fromhex(event["hex"])):
                    response = Response.decode(payload)
                    assert response.code == 0 and response.error is None
                    assert response.request_id in ids
                    count += 1
        assert not decoder.incomplete
    assert count == 39


def test_every_byte_fragmentation_escaping_and_multiple_packets():
    payload = bytes(range(256))
    decoder = FrameDecoder()
    result = []
    for value in frame(payload):
        result.extend(decoder.feed(bytes([value])))
    assert result == [payload]
    assert decoder.feed(b"\x00garbage" + frame(b"abc") + frame(b"def")) == [b"abc", b"def"]


def test_corrupt_crc_rejected_then_next_frame_works():
    decoder = FrameDecoder()
    bad = bytearray(frame(b"abc"))
    bad[1] ^= 1
    with pytest.raises(ProtocolError, match="CRC"):
        decoder.feed(bad)
    assert decoder.feed(frame(b"ok")) == [b"ok"]


@pytest.mark.parametrize("data", [b"\x80", b"\x00", b"\x0a\x05hi", b"\x0b", b"\x08" + b"\xff" * 10])
def test_invalid_protobuf(data):
    with pytest.raises(ProtocolError):
        Message(data)


def test_int32_and_oneof_wire_order():
    message = Message(sint32(2, -2) + blob(1, b"") + uint(2, 0))
    assert message.oneof({1, 2}) == 2
    assert message.int32(2) == 0
    assert Message(sint32(2, -2)).int32(2) == -2
    assert Message().oneof({1, 2}) is None


def test_id_is_uint32_not_signed_int32():
    decoder = FrameDecoder()
    body = decoder.feed(request("/fixture/Read", 0xFFFFFFFF))[0]
    assert Message(body).uint(3) == 0xFFFFFFFF
    assert Response.decode(uint(3, 0xFFFFFFFF)).request_id == 0xFFFFFFFF
    for value in (0, -1, 2**32):
        with pytest.raises(ProtocolError):
            request("/fixture/Read", value)


def test_crc_reference_and_stream_marker():
    assert zlib.crc32(b"123456789") == 0xCBF43926
    assert Response.decode(bytes.fromhex("18013803")).stream == Stream.START
    with pytest.raises(ProtocolError):
        Response.decode(uint(3, 1) + uint(7, 20))
