"""Compare a validated control request with the actual subsequent snapshot.

An RPC acknowledgement only proves receipt. A mismatch means the requested
state was not observed yet; it does not prove rejection and must never cause
an automatic retry. These checks do not establish hardware support or units.
"""

from . import cooktop, extractor, zone
from .wire import Message


def _get(value, *keys):
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def command_confirmed(command: tuple[str, bytes], snapshot: dict) -> bool:
    """Require the relevant state; absent nested messages are never zero/off."""
    path, body = command
    message = Message(body)
    if path.startswith(extractor.PREFIX):
        status = _get(snapshot, "extractor")
        settings = _get(status, "extractor_settings")
        method = path.removeprefix(extractor.PREFIX)
        if method == "SetExtractorMode":
            expected = extractor.decode_mode(message.bytes(1))
            return _get(settings, "extractor_mode") == expected
        if method == "SetDurationAfterRun":
            return _get(settings, "pure", "after_run_duration") == message.uint(1)
        if method == "StopAfterRun":
            return _get(status, "remaining_after_run_ms") == 0
        timer = _get(settings, "egg_timer")
        if method == "SetEggTimer":
            return _get(timer, "duration_raw") == message.uint(1)
        if method == "SetEggTimerState":
            return _get(timer, "running") == message.boolean(1)
    elif path.startswith(cooktop.PREFIX):
        settings = _get(snapshot, "cooktop", "cooktop_settings")
        method = path.removeprefix(cooktop.PREFIX)
        fields = {
            "SetPaused": "pause",
            "SetChildLock": "childlock_setting",
            "SetSignalVolume": "signal_volume",
        }
        if method in fields:
            return _get(settings, fields[method]) == message.int32(1)
        if method == "SetSpecificCooktopSetting":
            request = message.message(1)
            selected = request.oneof(set(range(1, 9)))
            pure = _get(settings, "pure")
            pure_fields = {
                1: "clean_lock",
                2: "permanent_child_lock",
                3: "sensitivity",
                5: "automatic_pot_detection",
                6: "max_op_duration",
            }
            if selected in pure_fields:
                return _get(pure, pure_fields[selected]) == request.message(selected).int32(1)
            if selected == 7:
                expected = cooktop.decode_disabled_functions(request.message(7).bytes(1))
                return _get(pure, "super_simple_mode", "disabled_functions") == expected
    elif path.startswith(zone.SERVICE_PATH):
        method = path.removeprefix(zone.SERVICE_PATH)
        status = _get(snapshot, "zones", message.text(2 if method == "StartOrModifyCsf" else 1))
        if _get(status, "settings_present") is not True:
            return False
        if method == "StartOrModifyCsf":
            expected = zone.decode_csf_parameter(message.bytes(1))
            actual = _get(status, "csf", "parameters")
            # This confirms a reported program, never heating, timer progress
            # or completion of the appliance's physical confirmation step.
            return (
                _get(status, "mode") == "csf"
                and _get(status, "csf", "phase") in {1, 2, 3}
                and all(
                    _get(actual, key) == value
                    for key, value in expected.items()
                    if key not in {"present_fields", "csf_time_to_set_obsolete"}
                )
            )
        if method == "SetMode":
            expected = zone.decode_settings(body)
            key = {
                "power_level": "power_level",
                "heat_retention": "keep_warm",
                "heat_up": "heat_up_power",
            }.get(expected["mode"])
            return (
                key is not None
                and _get(status, "mode") == expected["mode"]
                and _get(status, key) == expected[key]
            )
        if method == "StopCsf":
            # An expired/unknown CSF still is not proof that StopCsf left it.
            return _get(status, "mode") in {"power_level", "heat_retention", "heat_up"}
        if method == "SetTimer":
            return _get(status, "timer", "duration") == message.uint(2)
        if method == "SetTimerState":
            return _get(status, "timer", "running") == message.boolean(2)
    return False
