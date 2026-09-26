"""Recorded cooktop responses and exact static request bytes; no hardware."""

import json
from pathlib import Path

import pytest

from custom_components.bora.ble import cooktop
from custom_components.bora.ble.wire import FrameDecoder, ProtocolError, Response, blob, uint


def captured_status(name):
    capture = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())
    session = next(item for item in capture["sessions"] if item["name"] == name)
    decoder = FrameDecoder()
    for event in session["events"]:
        if event["event"] == "notification":
            for payload in decoder.feed(bytes.fromhex(event["hex"])):
                return cooktop.decode_status(Response.decode(payload).body)
    raise AssertionError("No recorded response")


def test_recorded_settings_and_diagnostics():
    status = captured_status("cooktop-status-1")
    settings = status["cooktop_settings"]
    assert {
        key: settings[key]
        for key in ("pause", "childlock_setting", "connectivity_setting", "signal_volume")
    } == {
        "pause": False,
        "childlock_setting": 2,
        "connectivity_setting": 4,
        "signal_volume": 2,
    }
    assert settings["pure"] == {
        "clean_lock": False,
        "permanent_child_lock": True,
        "sensitivity": 2,
        "automatic_pot_detection": False,
        "max_op_duration": 2,
        "super_simple_mode": {
            "active": False,
            "disabled_functions": {
                "cleaning_lock_disabled": False,
                "pause_disabled": False,
                "warming_disabled": False,
                "timer_disabled": False,
                "hot_key_disabled": False,
            },
        },
        "remaining_filter_lifetime_raw": 7234,
        "dealer_menu_config": {"extraction_type": 1, "power_management": 3, "demo_mode": False},
    }
    assert status["current_primary_device_errors"] == []
    assert all(
        value is False
        for key, value in status.items()
        if key not in {"cooktop_settings", "current_primary_device_errors"}
    )
    standby = captured_status("standby-cooktop-1")
    assert standby["ready_for_sleep"] is False
    assert standby["cooktop_settings"]["childlock_setting"] == 1
    assert standby["cooktop_settings"]["pure"]["remaining_filter_lifetime_raw"] == 7230


def test_absence_and_present_empty():
    assert cooktop.decode_status(b"")["cooktop_settings"] is None
    assert cooktop.decode_status(b"")["current_primary_device_errors"] is None
    status = cooktop.decode_status(bytes.fromhex("0a003a00"))
    assert status["cooktop_settings"]["pure"] is None
    assert status["current_primary_device_errors"] == []
    assert cooktop.decode_settings(blob(5, b""))["pure"]["super_simple_mode"] is None
    assert (
        cooktop.decode_pure_settings(blob(6, b""))["super_simple_mode"]["disabled_functions"]
        is None
    )


def test_unknown_enums_nested_merge_and_integer_types():
    settings = cooktop.decode_status(blob(1, uint(2, 99)) + blob(1, uint(4, 8)))["cooktop_settings"]
    assert settings["childlock_setting"] == 99
    assert settings["signal_volume"] == 8
    assert cooktop.decode_settings(bytes.fromhex("20ffffffffffffffffff01"))["signal_volume"] == -1
    assert (
        cooktop.decode_pure_settings(uint(7, 0xFFFFFFFF))["remaining_filter_lifetime_raw"]
        == 0xFFFFFFFF
    )
    with pytest.raises(ProtocolError):
        cooktop.decode_pure_settings(uint(7, 2**32))


def test_packed_unpacked_mixed_and_unknown_error_codes():
    assert cooktop.decode_errors(bytes.fromhex("08010a0302e7070803")) == [1, 2, 999, 3]
    assert cooktop.decode_errors(bytes.fromhex("08ffffffffffffffffff01")) == [-1]
    assert cooktop.decode_errors(bytes.fromhex("0a0affffffffffffffffff01")) == [-1]
    assert cooktop.decode_errors(bytes.fromhex("0a00")) == []
    assert cooktop.decode_errors(uint(2, 44)) == []


@pytest.mark.parametrize(
    "hex_body", ["0a0180", "0a0affffffffffffffffff02", "0d00000000", "0a0b8080808080808080808000"]
)
def test_malformed_errors(hex_body):
    with pytest.raises(ProtocolError):
        cooktop.decode_errors(bytes.fromhex(hex_body))


@pytest.mark.parametrize(
    "fn,args,method,expected",
    [
        (cooktop.get_status, (), "GetCooktopStatus", ""),
        (cooktop.get_settings, (), "GetCooktopSettings", ""),
        (cooktop.stream_status, (), "StreamCooktopStatusUpdates", ""),
        (cooktop.set_paused, (False,), "SetPaused", "0800"),
        (cooktop.set_paused, (True,), "SetPaused", "0801"),
        (cooktop.set_child_lock, (1,), "SetChildLock", "0801"),
        (cooktop.set_signal_volume, (9,), "SetSignalVolume", "0809"),
        (cooktop.set_cleaning_lock, (False,), "SetSpecificCooktopSetting", "0a040a020800"),
        (cooktop.set_permanent_child_lock, (True,), "SetSpecificCooktopSetting", "0a0412020801"),
        (cooktop.set_touch_sensitivity, (2,), "SetSpecificCooktopSetting", "0a041a020802"),
        (cooktop.set_led_test, (True,), "SetSpecificCooktopSetting", "0a0422020801"),
        (cooktop.set_automatic_pot_detection, (True,), "SetSpecificCooktopSetting", "0a042a020801"),
        (cooktop.set_maximum_op_duration, (3,), "SetSpecificCooktopSetting", "0a0432020803"),
        (cooktop.set_filter_unit, (), "SetSpecificCooktopSetting", "0a024200"),
        (cooktop.restart_connectivity_module, (), "RestartConnectivityModule", ""),
    ],
)
def test_request_wire_contract(fn, args, method, expected):
    assert fn(*args) == (cooktop.PREFIX + method, bytes.fromhex(expected))


def test_super_simple_complete_group_and_explicit_false():
    values = dict(
        cleaning_lock_disabled=False,
        pause_disabled=True,
        warming_disabled=False,
        timer_disabled=True,
        hot_key_disabled=False,
    )
    assert cooktop.set_super_simple_disabled_functions(**values) == (
        cooktop.PREFIX + "SetSpecificCooktopSetting",
        bytes.fromhex("0a0e3a0c0a0a08001001180020012800"),
    )
    with pytest.raises(TypeError):
        cooktop.set_super_simple_disabled_functions(pause_disabled=True)
    with pytest.raises(ProtocolError):
        cooktop.set_super_simple_disabled_functions(**(values | {"pause_disabled": 1}))


@pytest.mark.parametrize(
    "fn,value",
    [
        (cooktop.set_paused, 1),
        (cooktop.set_paused, "false"),
        (cooktop.set_child_lock, True),
        (cooktop.set_child_lock, 0),
        (cooktop.set_child_lock, 4),
        (cooktop.set_signal_volume, 2**31),
        (cooktop.set_signal_volume, 2.0),
        (cooktop.set_cleaning_lock, 0),
        (cooktop.set_permanent_child_lock, 1),
        (cooktop.set_touch_sensitivity, 0),
        (cooktop.set_touch_sensitivity, 4),
        (cooktop.set_led_test, 1),
        (cooktop.set_automatic_pot_detection, None),
        (cooktop.set_maximum_op_duration, 0),
        (cooktop.set_maximum_op_duration, 4),
    ],
)
def test_invalid_commands_fail_before_transport(fn, value):
    with pytest.raises(ProtocolError):
        fn(value)


def test_volume_constraints_are_indices():
    with pytest.raises(ProtocolError):
        cooktop.set_signal_volume(100, allowed_levels=list(range(10)))
    assert cooktop.set_signal_volume(9, allowed_levels=list(range(10)))[1] == bytes.fromhex("0809")


def test_error_labels_preserve_sdk_names_and_unknown_values():
    assert cooktop.ERROR_CODE_NAMES[0] == "UNSPECIFIED"
    assert cooktop.ERROR_CODE_NAMES[1] == "E_1_LEFT_FRONT"
    assert cooktop.ERROR_CODE_NAMES[11] == "H_LEFT_FRONT"
    assert cooktop.ERROR_CODE_NAMES[45] == "E_03"
    assert cooktop.ERROR_CODE_NAMES[56] == "U_400"
    assert cooktop.ERROR_CODE_NAMES[62] == "E_B_RIGHT_FRONT"
    assert cooktop.ERROR_CODE_NAMES[63] == "E_1_MID_BACK"
    assert cooktop.ERROR_CODE_NAMES[74] == "E_B_MID_BACK"
    assert cooktop.ERROR_CODE_NAMES[75] == "E_1_MID_FRONT"
    assert cooktop.ERROR_CODE_NAMES[86] == "E_B_MID_FRONT"
    assert cooktop.ERROR_CODE_NAMES.get(999) is None
