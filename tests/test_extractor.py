"""Golden schema encodings and sanitized recordings; no BLE I/O."""

import json
from pathlib import Path

import pytest

from custom_components.bora.ble import extractor
from custom_components.bora.ble.wire import FrameDecoder, ProtocolError, Response, blob, uint


def captured_statuses(name):
    capture = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())
    session = next(item for item in capture["sessions"] if item["name"] == name)
    decoder = FrameDecoder()
    result = []
    for event in session["events"]:
        if event["event"] == "notification":
            for payload in decoder.feed(bytes.fromhex(event["hex"])):
                response = Response.decode(payload)
                if response.body is not None:
                    result.append(extractor.decode_status(response.body))
    return result


def test_recorded_status_and_standby():
    assert captured_statuses("status-request-1")[0] == {
        "extractor_settings": {
            "egg_timer": {"duration_raw": 0, "remaining_raw": 0, "running": False},
            "extractor_mode": {"mode": "power_level", "power_level": 1},
            "pure": {"after_run_duration": 4, "after_run_minutes": 30},
        },
        "remaining_after_run_ms": 0,
    }
    assert (
        captured_statuses("standby-extractor-1")[0]["extractor_settings"]["extractor_mode"][
            "power_level"
        ]
        == 0
    )
    assert captured_statuses("status-request-3")[0]["remaining_after_run_ms"] == 1754000


def test_recorded_stream_countdown_and_manual_zero():
    statuses = captured_statuses("stream-observation-1")
    assert len(statuses) == 14
    assert [s["remaining_after_run_ms"] for s in statuses[:3]] == [1194000, 1189000, 1184000]
    assert [s["extractor_settings"]["extractor_mode"]["power_level"] for s in statuses[8:]] == [
        0,
        2,
        3,
        9,
        8,
        5,
    ]
    assert captured_statuses("stream-observation-2") == []


def test_absent_messages_differ_from_present_empty():
    assert extractor.decode_status(b"")["extractor_settings"] is None
    assert extractor.decode_settings(b"") == {
        "egg_timer": None,
        "extractor_mode": None,
        "pure": None,
    }
    settings = extractor.decode_settings(bytes.fromhex("0a0012001a00"))
    assert settings["egg_timer"] == {"duration_raw": 0, "remaining_raw": 0, "running": False}
    assert settings["extractor_mode"] == {"mode": None}
    assert settings["pure"] == {"after_run_duration": 0, "after_run_minutes": None}


def test_oneof_wire_order_and_signedness():
    assert extractor.decode_mode(bytes.fromhex("10000a00")) == {"mode": "auto"}
    assert extractor.decode_mode(bytes.fromhex("0a001000")) == {
        "mode": "power_level",
        "power_level": 0,
    }
    assert extractor.decode_mode(bytes.fromhex("10ffffffffffffffffff01"))["power_level"] == -1
    with pytest.raises(ProtocolError):
        extractor.decode_mode(bytes.fromhex("0801"))


def test_nested_fragments_merge_and_unknown_enum_survives():
    status = extractor.decode_status(blob(1, blob(1, uint(1, 123))) + blob(1, blob(1, uint(2, 99))))
    assert status["extractor_settings"]["egg_timer"] == {
        "duration_raw": 123,
        "remaining_raw": 99,
        "running": False,
    }
    assert extractor.decode_settings(blob(3, uint(1, 99)))["pure"] == {
        "after_run_duration": 99,
        "after_run_minutes": None,
    }
    assert extractor.decode_timer(uint(1, 0xFFFFFFFF))["duration_raw"] == 0xFFFFFFFF
    with pytest.raises(ProtocolError):
        extractor.decode_timer(uint(1, 2**32))


@pytest.mark.parametrize(
    "fn,args,method,expected",
    [
        (extractor.get_status, (), "GetExtractorStatus", ""),
        (extractor.get_settings, (), "GetExtractorSettings", ""),
        (extractor.stream_status, (), "StreamExtractorStatusUpdates", ""),
        (extractor.set_auto_mode, (), "SetExtractorMode", "0a020a00"),
        (extractor.set_power_level, (0,), "SetExtractorMode", "0a021000"),
        (extractor.set_power_level, (3,), "SetExtractorMode", "0a021003"),
        (extractor.set_after_run_duration, (4,), "SetDurationAfterRun", "0804"),
        (extractor.stop_after_run, (), "StopAfterRun", ""),
        (extractor.set_egg_timer, (0xFFFFFFFF,), "SetEggTimer", "08ffffffff0f"),
        (extractor.set_egg_timer_state, (False,), "SetEggTimerState", "0800"),
        (extractor.set_egg_timer_state, (True,), "SetEggTimerState", "0801"),
    ],
)
def test_request_wire_contract(fn, args, method, expected):
    assert fn(*args) == (extractor.PREFIX + method, bytes.fromhex(expected))


@pytest.mark.parametrize(
    "fn,value",
    [
        (extractor.set_power_level, True),
        (extractor.set_power_level, 1.5),
        (extractor.set_power_level, 2**31),
        (extractor.set_power_level, -(2**31) - 1),
        (extractor.set_after_run_duration, 0),
        (extractor.set_after_run_duration, 6),
        (extractor.set_egg_timer, -1),
        (extractor.set_egg_timer, 2**32),
        (extractor.set_egg_timer, True),
        (extractor.set_egg_timer_state, 1),
    ],
)
def test_invalid_commands_fail_before_transport(fn, value):
    with pytest.raises(ProtocolError):
        fn(value)


def test_advertised_constraints():
    with pytest.raises(ProtocolError):
        extractor.set_power_level(9, allowed_levels=[0, 1, 2])
    with pytest.raises(ProtocolError):
        extractor.set_after_run_duration(4, allowed_values=[3, 2, 1])
    with pytest.raises(ProtocolError):
        extractor.set_egg_timer(999, minimum=1000, maximum=7250000)
    with pytest.raises(ProtocolError):
        extractor.set_egg_timer(1000, minimum=1000, maximum=999)
    assert extractor.set_egg_timer(1000, minimum=1000, maximum=7250000)[1] == bytes.fromhex(
        "08e807"
    )
