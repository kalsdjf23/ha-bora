"""Offline identity/capability checks against a recorded X PURE descriptor."""

import json
from pathlib import Path

import pytest

from custom_components.bora.ble import identify
from custom_components.bora.ble.wire import (
    FrameDecoder,
    ProtocolError,
    Response,
    blob,
    sint32,
    string,
    uint,
)


def test_recorded_descriptor_preserves_labels_zones_and_capabilities():
    fixture = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())
    session = next(s for s in fixture["sessions"] if s["name"] == "device-descriptor-1")
    frames = FrameDecoder()
    responses = []
    for event in session["events"]:
        if event["event"] == "notification":
            responses += [Response.decode(p) for p in frames.feed(bytes.fromhex(event["hex"]))]
    assert len(responses) == 1  # Response split across two notifications.
    assert responses[0].code == 0
    descriptor = identify.decode_descriptor(responses[0].body)
    assert descriptor["zone_uids"] == {
        "left_down_zone_uid": "front_left",
        "left_upper_zone_uid": "back_left",
        "right_upper_zone_uid": "back_right",
        "right_down_zone_uid": "front_right",
        "mid_back_zone_uid": "",
        "mid_front_zone_uid": "",
    }
    zone = descriptor["zone_descriptor"]
    assert zone["power_levels"] == [{"index": i, "level_name": str(i)} for i in range(10)] + [
        {"index": 10, "level_name": "P"}
    ]
    assert zone["zone_mode_types"] == [1, 2, 3, 4]
    assert zone["variable_heat_retention_support"] is True
    assert zone["timer_limits"] == {"min_duration": 1000, "max_duration": 7250000}
    assert zone["zone_mode_descriptor"] == [
        {"u_id": "front_left", "supported_csf": [5, 1, 4, 2, 3]},
        {"u_id": "back_left", "supported_csf": [5, 1, 4, 2, 3]},
        {"u_id": "back_right", "supported_csf": [5, 1, 4, 2]},
        {"u_id": "front_right", "supported_csf": [5, 1, 4, 2]},
    ]
    extractor = descriptor["extractor_descriptor"]
    assert extractor["power_levels"] == [{"index": i, "level_name": str(i)} for i in range(9)] + [
        {"index": 9, "level_name": "P"}
    ]
    assert extractor["extractor_mode_types"] == [1, 2]
    assert extractor["type"] == 1
    assert extractor["egg_timer_limits"] == {"min_duration": 1000, "max_duration": 7250000}
    assert extractor["pure"]["after_run_durations"] == [3, 2, 1]
    assert descriptor["signal_volume_levels"][0] == {"index": 0, "level_name": "0%"}
    assert descriptor["signal_volume_levels"][-1] == {"index": 9, "level_name": "100%"}
    assert descriptor["pure"] == {
        "filter_unit_types": [{"index": 1, "filter": "PUAKF", "lifetime": 150}]
    }
    csf = descriptor["csf_descriptor"]
    assert csf["index_range"] == {"min": 1, "max": 5}
    assert csf["timer_limit"] == {"min_duration": 10000, "max_duration": 7250000}
    assert [x["csf_type"] for x in csf["type_descriptors"]] == [1, 5, 3, 2, 4, 6]
    assert csf["type_descriptors"][0] == {
        "csf_type": 1,
        "number_of_phases": 3,
        "csf_type_min_step_size": 1,
        "csf_type_max_step_size": 80,
        "csf_type_min_val": 60,
        "csf_type_max_val": 140,
    }


def test_information_wire_fields_and_repeated_part_metadata():
    # Synthetic identifiers; never commit the user's device serials.
    component = string(1, "PART") + string(2, "HW2") + string(3, "SW3") + string(4, "SER")
    body = (
        uint(1, 2)
        + string(2, "FD")
        + string(3, "MODEL")
        + blob(4, blob(1, component) + blob(1, b""))
        + string(5, "future field")  # Field 5 is not cmIdentifier.
        + string(6, "CM")
        + string(7, "CMHW")
        + string(8, "CMSW")
        + string(9, "CMSER")
    )
    assert identify.decode_information(body) == {
        "product": 2,
        "product_name": "x_pure",
        "fd": "FD",
        "e_nr": "MODEL",
        "cm_identifier": "CM",
        "cm_hw_version_no": "CMHW",
        "cm_sw_version_no": "CMSW",
        "cm_serial_number": "CMSER",
        "pure": {
            "product_meta_data": [
                {
                    "part_identifier": "PART",
                    "device_hw_version_no": "HW2",
                    "device_sw_version_no": "SW3",
                    "serial_number": "SER",
                },
                {
                    "part_identifier": "",
                    "device_hw_version_no": "",
                    "device_sw_version_no": "",
                    "serial_number": "",
                },
            ]
        },
    }


def test_absent_nested_descriptors_are_not_zero_capabilities():
    assert identify.decode_descriptor(b"") == {
        "zone_uids": None,
        "zone_descriptor": None,
        "extractor_descriptor": None,
        "signal_volume_levels": [],
        "csf_descriptor": None,
        "pure": None,
    }
    present = identify.decode_descriptor(blob(2, b"") + blob(3, blob(5, b"")) + blob(6, b""))
    assert present["zone_descriptor"]["power_levels"] == []
    assert present["zone_descriptor"]["timer_limits"] is None
    assert present["extractor_descriptor"]["pure"] == {"after_run_durations": []}
    assert present["pure"] == {"filter_unit_types": []}
    assert identify.decode_information(b"")["pure"] is None
    assert identify.decode_information(blob(4, b""))["pure"] == {"product_meta_data": []}


def test_split_descriptor_messages_merge_limits_and_repeated_levels():
    first = blob(1, uint(1, 1000)) + uint(2, 1) + blob(3, uint(1, 0) + string(2, "0"))
    second = blob(1, uint(2, 7250000)) + blob(3, uint(1, 1) + string(2, "1"))
    zone = identify.decode_descriptor(blob(2, first) + blob(2, second))["zone_descriptor"]
    assert zone["timer_limits"] == {"min_duration": 1000, "max_duration": 7250000}
    assert zone["zone_mode_types"] == [1]
    assert zone["power_levels"] == [
        {"index": 0, "level_name": "0"},
        {"index": 1, "level_name": "1"},
    ]


def test_earlier_malformed_nested_descriptor_is_not_hidden_by_later_value():
    with pytest.raises(ProtocolError):
        identify.decode_descriptor(uint(2, 1) + blob(2, b""))


def test_enum_lists_accept_mixed_packed_unpacked_and_unknown_values():
    zone = uint(2, 1) + blob(2, bytes.fromhex("028101")) + sint32(2, -1)
    descriptor = identify.decode_descriptor(blob(2, zone))
    assert descriptor["zone_descriptor"]["zone_mode_types"] == [1, 2, 129, -1]
    assert identify.decode_zone_descriptor(zone) == descriptor["zone_descriptor"]
    assert identify.decode_information(uint(1, 129))["product_name"] == "unknown_129"


@pytest.mark.parametrize("packed", [b"\x80", b"\x80" * 10, b"\xff" * 9 + b"\x02"])
def test_malformed_packed_enums_are_rejected(packed):
    with pytest.raises(ProtocolError):
        identify.decode_descriptor(blob(2, blob(2, packed)))


def test_wrong_known_field_types_and_invalid_strings_are_rejected():
    with pytest.raises(ProtocolError):
        identify.decode_descriptor(uint(2, 1))
    with pytest.raises(ProtocolError):
        identify.decode_descriptor(blob(2, bytes.fromhex("1500000000")))
    with pytest.raises(ProtocolError):
        identify.decode_information(blob(6, b"\xff"))


def test_power_and_filter_descriptor_signedness_and_labels():
    power = sint32(1, -1) + string(2, "future")
    filter_unit = sint32(1, -2) + string(2, "TEST") + sint32(3, -3)
    descriptor = identify.decode_descriptor(blob(4, power) + blob(6, blob(1, filter_unit)))
    assert descriptor["signal_volume_levels"] == [{"index": -1, "level_name": "future"}]
    assert descriptor["pure"]["filter_unit_types"] == [
        {"index": -2, "filter": "TEST", "lifetime": -3}
    ]


def test_safe_read_requests_have_exact_paths_and_empty_bodies():
    assert identify.get_information() == (
        "/bora.generic.identify.v1.IdentifyService/GetSystemInformation",
        b"",
    )
    assert identify.get_descriptor() == (
        "/bora.generic.identify.v1.IdentifyService/GetSystemValueRangeDescriptor",
        b"",
    )
    assert identify.get_wifi_status() == (
        "/bora.generic.wifi.v1.WiFiProvisioningService/GetWiFiStatus",
        b"",
    )
    assert identify.get_heartbeat_status() == (
        "/bora.generic.debug.v1.DebugService/GetHeartbeatStatus",
        b"",
    )
    assert identify.get_heartbeat_period() == (
        "/bora.generic.heartbeat.v1.HeartbeatService/GetHeartbeatPeriod",
        b"",
    )
    assert identify.get_saved_csf() == ("/bora.generic.csf.v1.CsfService/GetSavedCsf", b"")
    assert identify.list_sys_events(5) == (
        "/bora.generic.logging.sysevent.v1.SysEventService/ListSysEvents",
        b"\x08\x05",
    )
    assert identify.list_user_events(5) == (
        "/bora.generic.logging.userevent.v1.UserEventService/ListUserEvents",
        b"\x08\x05",
    )


@pytest.mark.parametrize("count", [0, -1, 101, True, 2.5, "20"])
def test_list_requests_have_a_bounded_positive_count(count):
    with pytest.raises(ValueError):
        identify.list_sys_events(count)
    with pytest.raises(ValueError):
        identify.list_user_events(count)


def test_wifi_unary_wrapper_differs_from_direct_stream_message():
    status = (
        uint(1, 9)
        + string(2, "Test Network")
        + blob(3, bytes.fromhex("aabbccddeeff"))
        + uint(4, 0xC0000201)
        + string(5, "UTC0")
    )
    expected = {
        "connection_status": 9,
        "connection_status_name": "internet_access",
        "ssid": "Test Network",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "ip_v4_address": 0xC0000201,
        "posix_time_zone": "UTC0",
    }
    assert identify.decode_wifi_status(blob(1, status)) == expected
    assert identify.decode_wifi_status_update(status) == expected
    assert identify.decode_wifi_status(b"") is None
    assert identify.decode_wifi_status(blob(1, b""))["connection_status"] == 0
    assert identify.decode_wifi_status_update(uint(1, 99))["connection_status_name"] == "unknown_99"


def test_heartbeat_counter_is_unsigned_and_event_timestamps_stay_raw():
    assert identify.decode_heartbeat_status(bytes.fromhex("080110ffffffff0f189827")) == {
        "heartbeat_request_active": True,
        "heartbeat_counter": 2**32 - 1,
        "heartbeat_period": 5016,
    }
    assert identify.decode_heartbeat_period(bytes.fromhex("089827")) == {"heartbeat_period": 5016}
    event = bytes.fromhex("08ffffffff0f1063")
    assert identify.decode_event(event) == {"timestamp": 2**32 - 1, "event_type": 99}
    assert identify.decode_events(blob(1, event) + blob(1, b"")) == [
        {"timestamp": 2**32 - 1, "event_type": 99},
        {"timestamp": 0, "event_type": 0},
    ]


def test_saved_csf_uses_shared_signed_parameter_decoder():
    parameter = uint(1, 7) + uint(3, 2) + sint32(8, -10) + uint(9, 80)
    result = identify.decode_saved_csf(blob(1, parameter))
    assert len(result) == 1
    assert result[0]["csf_id"] == 7
    assert result[0]["csf_index"] == 2
    assert result[0]["csf_target_min_val"] == -10
    assert result[0]["csf_target_max_val"] == 80
    assert identify.decode_saved_csf(b"") == []
    with pytest.raises(ProtocolError):
        identify.decode_saved_csf(uint(1, 0))


@pytest.mark.parametrize(
    "decoder,body",
    [
        (identify.decode_heartbeat_period, uint(1, 2**32)),
        (identify.decode_heartbeat_status, uint(2, 2**32)),
        (identify.decode_event, uint(1, 2**32)),
        (identify.decode_wifi_status_update, uint(4, 2**32)),
        (identify.decode_descriptor, blob(2, blob(1, uint(1, 2**32)))),
    ],
)
def test_uint32_fields_reject_overflow(decoder, body):
    with pytest.raises(ProtocolError):
        decoder(body)
