"""Event labels preserve their namespace, raw values and uninterpreted history."""

import pytest

from custom_components.bora.ble import identify
from custom_components.bora.ble.wire import ProtocolError, blob, sint32, uint


@pytest.mark.parametrize(
    "event_type,system_name,user_name",
    [
        (0, "EVENT_TYPE_UNSPECIFIED", "EVENT_TYPE_UNSPECIFIED"),
        (1, "EVENT_TYPE_BLE_MANAGER_STARTED", "EVENT_TYPE_COOKTOP_DATA_UPDATE"),
        (5, "EVENT_TYPE_BLE_SERVER_STARTED", "EVENT_TYPE_EXTRACTOR_DATA_UPDATE"),
        (9, "EVENT_TYPE_BLE_SERVER_UPDATE_DEVICE_INFO_SERVICE", "EVENT_TYPE_ZONE_DATA_FL_UPDATE"),
        (13, "EVENT_TYPE_BLE_PEER_SUBSCRIBED", "EVENT_TYPE_CONNECTIVITY_UPDATE"),
        (16, "EVENT_TYPE_BLE_CONNECTION_STATE", "EVENT_TYPE_CONNECTIVITY_DATA_RESERVE_3"),
        (17, "EVENT_TYPE_BLE_RESERVE_1", "unknown_17"),
        (33, "EVENT_TYPE_WIFI_CONNECTED", "unknown_33"),
        (47, "EVENT_TYPE_WIFI_DHCP_TIMEOUT", "unknown_47"),
        (65, "EVENT_TYPE_WIFI_STATUS_INVALID_PASSWORD", "unknown_65"),
        (83, "EVENT_TYPE_ENERGY_STANDBY_FOR", "unknown_83"),
        (91, "EVENT_TYPE_CSF_SAVED_PRESET_TO_NVS", "unknown_91"),
        (98, "EVENT_TYPE_NO_HOST_DEVICE", "unknown_98"),
        (99, "EVENT_TYPE_ESP_LOG", "unknown_99"),
        (100, "unknown_100", "unknown_100"),
        (-1, "unknown_-1", "unknown_-1"),
    ],
)
def test_labels_use_the_recorded_namespace_and_keep_unknown_codes(
    event_type, system_name, user_name
):
    body = uint(1, 2**32 - 1) + sint32(2, event_type)
    raw = {"timestamp": 2**32 - 1, "event_type": event_type}
    assert identify.decode_sys_event(body) == {**raw, "event_type_name": system_name}
    assert identify.decode_user_event(body) == {**raw, "event_type_name": user_name}
    # The generic API has no namespace and remains backward compatible.
    assert identify.decode_event(body) == raw
    assert identify.decode_events(blob(1, body)) == [raw]


@pytest.mark.parametrize(
    "decode_one,decode_list",
    [
        (identify.decode_sys_event, identify.decode_sys_events),
        (identify.decode_user_event, identify.decode_user_events),
    ],
)
def test_event_lists_keep_duplicates_and_wire_order_without_timestamp_conversion(
    decode_one, decode_list
):
    events = [uint(1, 5000) + uint(2, 1), uint(1, 3) + uint(2, 5), b""]
    payload = blob(1, events[0]) + blob(7, b"future field") + blob(1, events[1])
    payload += blob(1, events[1]) + blob(1, events[2])
    result = decode_list(payload)
    assert result == [decode_one(events[index]) for index in (0, 1, 1, 2)]
    assert [event["timestamp"] for event in result] == [5000, 3, 3, 0]
    assert result[-1] == {
        "timestamp": 0, "event_type": 0, "event_type_name": "EVENT_TYPE_UNSPECIFIED"
    }
    assert decode_list(b"") == []
    # Mutating one result cannot alter another equal event or a future decode.
    result[1]["event_type_name"] = "changed"
    assert result[2] == decode_one(events[1])
    assert decode_list(blob(1, events[1])) == [result[2]]


@pytest.mark.parametrize("decoder", [identify.decode_sys_events, identify.decode_user_events])
@pytest.mark.parametrize(
    "body",
    [
        uint(1, 0),  # A repeated event must be a message.
        blob(1, uint(1, 2**32)),  # The raw timestamp still has a uint32 limit.
        blob(1, blob(2, b"wrong type")),
        b"\x0a\x80",  # Truncated outer length.
        blob(1, b"\x08\x80"),  # Truncated event timestamp.
    ],
)
def test_named_event_lists_keep_protocol_validation(decoder, body):
    with pytest.raises(ProtocolError):
        decoder(body)
