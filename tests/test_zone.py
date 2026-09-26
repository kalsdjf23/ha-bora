"""Zone codec checks against recordings and independently specified wire bytes.

Passing these tests does not establish appliance support for control methods.
"""

import json
from pathlib import Path

import pytest

from custom_components.bora.ble import zone
from custom_components.bora.ble.wire import FrameDecoder, Message, ProtocolError, Response


def test_recorded_status_for_all_four_zones():
    fixture = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())
    observed = set()
    for session in fixture["sessions"]:
        if not session["name"].startswith("zone-status-"):
            continue
        decoder = FrameDecoder()
        for event in session["events"]:
            if event["event"] != "notification":
                continue
            for payload in decoder.feed(bytes.fromhex(event["hex"])):
                response = Response.decode(payload)
                assert response.code == 0
                assert response.body is not None
                status = zone.decode_status(response.body)
                observed.add(status["uid"])
                assert status["mode"] == "power_level"
                assert status["power_level"] == 0
                assert status["residual_heat"] is False
                assert status["pot_detection_active"] is True
                assert status["bridged"] is False
                assert status["timer"]["duration"] == 0
                assert status["timer"]["present_fields"] == ()
    assert observed == {"front_left", "back_left", "back_right", "front_right"}


def test_absent_mode_differs_from_explicit_power_zero():
    assert zone.decode_status(bytes.fromhex("0a030a0175"))["power_level"] is None
    zero = zone.decode_status(bytes.fromhex("0a070a017512020800"))
    assert zero["power_level"] == 0
    assert zero["mode"] == "power_level"
    assert zone.decode_status(b"")["settings_present"] is False


def test_last_oneof_wins_including_nested_pure():
    # Both power=7 and pure(retention=2, then heat-up=4) occur on the wire.
    settings = bytes.fromhex("0a0175120c08071a080a02080212020804")
    status = zone.decode_settings(settings)
    assert status["mode"] == "heat_up"
    assert status["heat_up_power"] == 4
    assert status["power_level"] is None
    assert status["keep_warm"] is None


def test_unknown_retention_enum_is_preserved():
    status = zone.decode_settings(bytes.fromhex("0a017512061a040a020863"))
    assert status["mode"] == "heat_retention"
    assert status["keep_warm"] == 99


def test_unknown_mode_is_not_reported_as_off():
    status = zone.decode_settings(bytes.fromhex("0a017512022801"))
    assert status["mode"] == "unknown"
    assert status["power_level"] is None


@pytest.mark.parametrize(
    ("factory", "method", "expected"),
    [
        (lambda: zone.get_status("u"), "GetZoneStatus", "0a0175"),
        (lambda: zone.get_settings("u"), "GetZoneSettings", "0a0175"),
        (zone.get_descriptor, "GetZoneValueDescriptor", ""),
        (lambda: zone.set_power("u", 0), "SetMode", "0a017512020800"),
        (lambda: zone.set_power("u", 10), "SetMode", "0a01751202080a"),
        (lambda: zone.set_keep_warm("u", "keep_warm"), "SetMode", "0a017512061a040a020802"),
        (lambda: zone.set_heat_up("u", 3), "SetMode", "0a017512061a0412020803"),
        (lambda: zone.set_timer("u", 1000), "SetTimer", "0a017510e807"),
        (lambda: zone.set_timer_state("u", False), "SetTimerState", "0a01751000"),
        (lambda: zone.set_timer_state("u", True), "SetTimerState", "0a01751001"),
        (lambda: zone.set_bridged("u", "v"), "SetBridged", "0a0175120176"),
        (lambda: zone.stop_csf("u"), "StopCsf", "0a0175"),
        (
            lambda: zone.start_or_modify_csf("u", {"csf_type": 2, "csf_type_target_value": 180}),
            "StartOrModifyCsf",
            "0a05200228b401120175",
        ),
    ],
)
def test_request_golden_bytes(factory, method, expected):
    path, body = factory()
    assert path == "/bora.generic.zone.v1.ZoneService/" + method
    assert body.hex() == expected


def test_timer_raw_uint32_and_presence():
    timer = zone.decode_timer(bytes.fromhex("08ffffffff0f10e8071801"))
    assert timer == {
        "duration": 2**32 - 1,
        "remaining": 1000,
        "running": True,
        "present_fields": (1, 2, 3),
    }
    _, body = zone.set_timer("u", 2**32 - 1)
    assert body.hex() == "0a017510ffffffff0f"


def test_bridge_response_contains_two_settings():
    # settings1: u -> v; settings2: v -> u.
    response = zone.decode_bridged(bytes.fromhex("0a080a017520012a017612080a017620012a0175"))
    assert response["settings1"]["uid"] == "u"
    assert response["settings1"]["bridged_to_uid"] == "v"
    assert response["settings2"]["uid"] == "v"
    assert response["settings2"]["bridged_to_uid"] == "u"
    assert zone.decode_bridged(b"") == {"settings1": None, "settings2": None}


def test_csf_sparse_fields_signed_bounds_and_obsolete_timer():
    parameters = {
        "csf_id": 7,
        "csf_index": 3,
        "csf_type": 1,
        "csf_type_target_value": 90,
        "csf_target_step_size": 1,
        "csf_target_min_val": -20,
        "csf_target_max_val": 140,
        "csf_settings": 0,
        "csf_timer_duration": 10000,
    }
    body = zone.encode_csf_parameter(parameters)
    parsed = Message(body)
    assert tuple(field.number for field in parsed.fields) == (1, 3, 4, 5, 7, 8, 9, 10, 11)
    assert parsed.int32(8) == -20
    decoded = zone.decode_csf_parameter(body + bytes.fromhex("320308e807"))
    assert {key: decoded[key] for key in parameters} == parameters
    assert decoded["csf_time_to_set_obsolete"]["duration"] == 1000


def test_csf_status_preserves_unknown_phase_and_type():
    csf = zone.decode_csf_status(bytes.fromhex("0a0220631063"))
    assert csf["phase"] == 99
    assert csf["parameters"]["csf_type"] == 99
    assert zone.decode_csf_status(b"")["parameters"] is None


def test_negative_unknown_csf_enum_is_not_treated_as_unsigned_counter():
    parameters = zone.decode_csf_parameter(bytes.fromhex("20ffffffffffffffffff01"))
    assert parameters["csf_type"] == -1


@pytest.mark.parametrize(
    "factory",
    [
        lambda: zone.get_status(""),
        lambda: zone.get_status(42),
        lambda: zone.get_status("\ud800"),
        lambda: zone.set_power("u", True),
        lambda: zone.set_power("u", -1),
        lambda: zone.set_power("u", 1.0),
        lambda: zone.set_power("u", 2**31),
        lambda: zone.set_power("u", 10, allowed_levels={0, 1}),
        lambda: zone.set_keep_warm("u", "boiling"),
        lambda: zone.set_keep_warm("u", 0),
        lambda: zone.set_keep_warm("u", True),
        lambda: zone.set_heat_up("u", 10, allowed_levels={0, 1}),
        lambda: zone.set_timer("u", -1),
        lambda: zone.set_timer("u", 2**32),
        lambda: zone.set_timer("u", 100, minimum=1000),
        lambda: zone.set_timer("u", 2000, maximum=1000),
        lambda: zone.set_timer("u", 1000, minimum=2000, maximum=1000),
        lambda: zone.set_timer_state("u", 1),
        lambda: zone.set_bridged("u", ""),
        lambda: zone.set_bridged("u", "u"),
        lambda: zone.encode_csf_parameter({}),
        lambda: zone.encode_csf_parameter({"unknown": 1}),
        lambda: zone.encode_csf_parameter({"csf_type": 99}),
        lambda: zone.encode_csf_parameter({"csf_id": -1}),
        lambda: zone.encode_csf_parameter({"csf_settings": True}),
        lambda: zone.encode_csf_parameter({"csf_target_min_val": -(2**31) - 1}),
    ],
)
def test_invalid_control_arguments_fail_before_io(factory):
    with pytest.raises(ProtocolError):
        factory()


@pytest.mark.parametrize(
    ("decoder", "body"),
    [
        (zone.decode_status, "0801"),  # settings encoded as a scalar
        (zone.decode_settings, "0a01ff"),  # invalid UID UTF-8
        (zone.decode_settings, "12030a0100"),  # power encoded as bytes
        (zone.decode_timer, "088080808010"),  # uint32 overflow
        (zone.decode_csf_parameter, "188080808010"),  # uint32 overflow
        (zone.decode_status, "0a05"),  # truncated message
    ],
)
def test_malformed_payloads_are_rejected(decoder, body):
    with pytest.raises(ProtocolError):
        decoder(bytes.fromhex(body))
