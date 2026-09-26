"""Readback comparisons only: no connection, HA runtime or appliance I/O."""

from copy import deepcopy

import pytest

from custom_components.bora.ble import cooktop, extractor, zone
from custom_components.bora.ble.confirmation import command_confirmed
from custom_components.bora.ble.wire import blob, sint32, string

UID = "front_left"
OTHER_UID = "back_right"
EXTRACTOR_SETTINGS = ("extractor", "extractor_settings")
COOKTOP_SETTINGS = ("cooktop", "cooktop_settings")


def with_field(path, value):
    """Build a minimal observed snapshot without inventing other readings."""
    snapshot = {}
    parent = snapshot
    for key in path[:-1]:
        parent = parent.setdefault(key, {})
    parent[path[-1]] = deepcopy(value)
    return snapshot


@pytest.mark.parametrize(
    ("command", "path", "observed", "different"),
    [
        (
            extractor.set_power_level(3),
            (*EXTRACTOR_SETTINGS, "extractor_mode"),
            {"mode": "power_level", "power_level": 3},
            {"mode": "power_level", "power_level": 0},
        ),
        (
            extractor.set_power_level(0),
            (*EXTRACTOR_SETTINGS, "extractor_mode"),
            {"mode": "power_level", "power_level": 0},
            {"mode": "auto"},
        ),
        (
            extractor.set_auto_mode(),
            (*EXTRACTOR_SETTINGS, "extractor_mode"),
            {"mode": "auto"},
            {"mode": None},
        ),
        (
            extractor.set_after_run_duration(2),
            (*EXTRACTOR_SETTINGS, "pure", "after_run_duration"),
            2,
            3,
        ),
        (extractor.stop_after_run(), ("extractor", "remaining_after_run_ms"), 0, 1000),
        (
            extractor.set_egg_timer(33000),
            (*EXTRACTOR_SETTINGS, "egg_timer", "duration_raw"),
            33000,
            33,
        ),
        (
            extractor.set_egg_timer(0),
            (*EXTRACTOR_SETTINGS, "egg_timer", "duration_raw"),
            0,
            33000,
        ),
        (
            extractor.set_egg_timer_state(True),
            (*EXTRACTOR_SETTINGS, "egg_timer", "running"),
            True,
            False,
        ),
        (
            extractor.set_egg_timer_state(False),
            (*EXTRACTOR_SETTINGS, "egg_timer", "running"),
            False,
            True,
        ),
        (cooktop.set_paused(True), (*COOKTOP_SETTINGS, "pause"), True, False),
        (cooktop.set_paused(False), (*COOKTOP_SETTINGS, "pause"), False, True),
        (cooktop.set_child_lock(2), (*COOKTOP_SETTINGS, "childlock_setting"), 2, 1),
        (cooktop.set_signal_volume(0), (*COOKTOP_SETTINGS, "signal_volume"), 0, 3),
        (cooktop.set_signal_volume(3), (*COOKTOP_SETTINGS, "signal_volume"), 3, 0),
        (cooktop.set_cleaning_lock(True), (*COOKTOP_SETTINGS, "pure", "clean_lock"), True, False),
        (cooktop.set_cleaning_lock(False), (*COOKTOP_SETTINGS, "pure", "clean_lock"), False, True),
        (
            cooktop.set_permanent_child_lock(True),
            (*COOKTOP_SETTINGS, "pure", "permanent_child_lock"),
            True,
            False,
        ),
        (
            cooktop.set_permanent_child_lock(False),
            (*COOKTOP_SETTINGS, "pure", "permanent_child_lock"),
            False,
            True,
        ),
        (cooktop.set_touch_sensitivity(3), (*COOKTOP_SETTINGS, "pure", "sensitivity"), 3, 2),
        (
            cooktop.set_automatic_pot_detection(True),
            (*COOKTOP_SETTINGS, "pure", "automatic_pot_detection"),
            True,
            False,
        ),
        (
            cooktop.set_automatic_pot_detection(False),
            (*COOKTOP_SETTINGS, "pure", "automatic_pot_detection"),
            False,
            True,
        ),
        (cooktop.set_maximum_op_duration(3), (*COOKTOP_SETTINGS, "pure", "max_op_duration"), 3, 2),
    ],
)
def test_setting_requires_the_requested_value_and_present_parents(
    command, path, observed, different
):
    snapshot = with_field(path, observed)
    assert command_confirmed(command, snapshot) is True
    assert command_confirmed(command, with_field(path, different)) is False

    # Removing any parent or leaf must not confirm zero/False through defaults.
    for depth in range(len(path)):
        missing = deepcopy(snapshot)
        parent = missing
        for key in path[:depth]:
            parent = parent[key]
        parent.pop(path[depth])
        assert command_confirmed(command, missing) is False
        parent[path[depth]] = None
        assert command_confirmed(command, missing) is False


@pytest.mark.parametrize("all_disabled", [False, True])
def test_simple_mode_requires_the_entire_requested_group(all_disabled):
    expected = {
        "cleaning_lock_disabled": all_disabled,
        "pause_disabled": all_disabled,
        "warming_disabled": all_disabled,
        "timer_disabled": all_disabled,
        "hot_key_disabled": all_disabled,
    }
    command = cooktop.set_super_simple_disabled_functions(**expected)
    group_path = (*COOKTOP_SETTINGS, "pure", "super_simple_mode", "disabled_functions")
    assert command_confirmed(command, with_field(group_path, expected)) is True

    for field in expected:
        different = {**expected, field: not expected[field]}
        assert command_confirmed(command, with_field(group_path, different)) is False
        partial = {key: value for key, value in expected.items() if key != field}
        assert command_confirmed(command, with_field(group_path, partial)) is False
    for missing in (None, {}):
        assert command_confirmed(command, with_field(group_path, missing)) is False
    assert command_confirmed(command, {"cooktop": {"cooktop_settings": {"pure": None}}}) is False


def test_simple_mode_confirms_mixed_flags_without_inferring_active_state():
    expected = {
        "cleaning_lock_disabled": True,
        "pause_disabled": False,
        "warming_disabled": True,
        "timer_disabled": False,
        "hot_key_disabled": True,
    }
    command = cooktop.set_super_simple_disabled_functions(**expected)
    for active in (False, True):
        snapshot = with_field(
            (*COOKTOP_SETTINGS, "pure", "super_simple_mode"),
            {"active": active, "disabled_functions": expected},
        )
        assert command_confirmed(command, snapshot) is True


@pytest.mark.parametrize(
    ("command", "mode", "field", "value"),
    [
        (zone.set_power(UID, 0), "power_level", "power_level", 0),
        (zone.set_power(UID, 3), "power_level", "power_level", 3),
        (zone.set_keep_warm(UID, 2), "heat_retention", "keep_warm", 2),
        (zone.set_heat_up(UID, 4), "heat_up", "heat_up_power", 4),
    ],
)
def test_zone_mode_requires_target_zone_mode_and_value(command, mode, field, value):
    status = {"uid": UID, "settings_present": True, "mode": mode, field: value}
    assert command_confirmed(command, {"zones": {UID: status}}) is True
    assert command_confirmed(command, {"zones": {OTHER_UID: status}}) is False
    assert command_confirmed(command, {"zones": {UID: None, OTHER_UID: status}}) is False
    for replacement in ({field: value + 1}, {"mode": "unknown"}, {"mode": "csf"}):
        wrong = {**status, **replacement}
        assert command_confirmed(command, {"zones": {UID: wrong, OTHER_UID: status}}) is False
    incomplete = {key: item for key, item in status.items() if key != field}
    assert command_confirmed(command, {"zones": {UID: incomplete}}) is False
    for presence in (False, None):
        assert command_confirmed(
            command, {"zones": {UID: {**status, "settings_present": presence}}}
        ) is False


@pytest.mark.parametrize(
    ("command", "field", "expected", "different"),
    [
        (zone.set_timer(UID, 0), "duration", 0, 33000),
        (zone.set_timer(UID, 33000), "duration", 33000, 33),
        (zone.set_timer_state(UID, False), "running", False, True),
        (zone.set_timer_state(UID, True), "running", True, False),
    ],
)
def test_zone_timer_compares_raw_field_on_the_requested_zone(command, field, expected, different):
    status = {"settings_present": True, "timer": {field: expected}}
    assert command_confirmed(command, {"zones": {UID: status}}) is True
    assert command_confirmed(command, {"zones": {OTHER_UID: status}}) is False
    wrong = {**status, "timer": {field: different}}
    assert command_confirmed(command, {"zones": {UID: wrong, OTHER_UID: status}}) is False
    for timer in (None, {}):
        assert command_confirmed(command, {"zones": {UID: {**status, "timer": timer}}}) is False
    assert command_confirmed(command, {"zones": {UID: {"settings_present": True}}}) is False
    assert command_confirmed(
        command, {"zones": {UID: {**status, "settings_present": False}}}
    ) is False


@pytest.mark.parametrize("mode", ["power_level", "heat_retention", "heat_up"])
def test_stop_csf_requires_observed_exit_to_a_known_alternative(mode):
    status = {"settings_present": True, "mode": mode}
    assert command_confirmed(zone.stop_csf(UID), {"zones": {UID: status}}) is True
    assert command_confirmed(zone.stop_csf(UID), {"zones": {OTHER_UID: status}}) is False


@pytest.mark.parametrize("mode", ["csf", "unknown", None, "future_mode"])
def test_stop_csf_is_not_confirmed_by_expired_unknown_or_missing_mode(mode):
    status = {"settings_present": True, "mode": mode, "csf": {"phase": 4}}
    assert command_confirmed(zone.stop_csf(UID), {"zones": {UID: status}}) is False


def test_decoded_explicit_zero_and_false_differ_from_absent_messages():
    command = extractor.set_power_level(0)
    manual_zero = extractor.decode_status(blob(1, blob(2, sint32(2, 0))))
    assert command_confirmed(command, {"extractor": manual_zero}) is True
    for body in (b"", blob(1, b""), blob(1, blob(2, b""))):
        assert command_confirmed(command, {"extractor": extractor.decode_status(body)}) is False

    command = cooktop.set_cleaning_lock(False)
    # A present empty Pure message supplies its protobuf scalar False default.
    assert command_confirmed(
        command, {"cooktop": cooktop.decode_status(blob(1, blob(5, b"")))}
    ) is True
    for body in (b"", blob(1, b"")):
        assert command_confirmed(command, {"cooktop": cooktop.decode_status(body)}) is False

    command = zone.set_timer_state(UID, False)
    present_timer = zone.decode_status(blob(1, string(1, UID) + blob(3, b"")))
    assert command_confirmed(command, {"zones": {UID: present_timer}}) is True
    absent_timer = zone.decode_status(blob(1, string(1, UID)))
    assert command_confirmed(command, {"zones": {UID: absent_timer}}) is False


@pytest.mark.parametrize(
    "command",
    [
        ("/unknown/SetMode", b""),
        (extractor.PREFIX + "UnknownMethod", b""),
        (cooktop.PREFIX + "UnknownMethod", b""),
        (zone.SERVICE_PATH + "UnknownMethod", string(1, UID)),
        cooktop.set_led_test(False),
        cooktop.set_filter_unit(),
        (cooktop.PREFIX + "SetSpecificCooktopSetting", blob(1, b"")),
        (zone.SERVICE_PATH + "SetMode", string(1, UID) + blob(2, b"")),
    ],
)
def test_unknown_or_unhandled_method_never_confirms(command):
    snapshot = {
        "extractor": {"extractor_settings": {}, "remaining_after_run_ms": 0},
        "cooktop": {"cooktop_settings": {"pure": {}}},
        "zones": {UID: {"settings_present": True, "mode": "power_level", "power_level": 0}},
    }
    assert command_confirmed(command, snapshot) is False


def test_timer_duration_confirmation_ignores_elapsed_remaining_time():
    # The requested raw duration is relevant; ticking remaining/running values are not.
    snapshot = {
        "zones": {
            UID: {
                "settings_present": True,
                "timer": {"duration": 33000, "remaining": 31500, "running": True},
            }
        }
    }
    assert command_confirmed(zone.set_timer(UID, 33000), snapshot) is True
