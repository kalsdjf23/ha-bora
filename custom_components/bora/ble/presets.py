"""Pure preparation of four catalogued X PURE frying presets; no I/O.

Only factual catalogue metadata is included. No recipe prose or images are
distributed. The app's temporary-start path supplies CSF index 0 and converts
explicit seconds to milliseconds. Its production mapper sets csfSettings from
!cooktopTimer; all four source records have cooktopTimer=true, hence 0.
Their absent timer input maps to a demonstrated 0 ms app-start default; see
docs/ASSIST-PRESETS.md. This is a catalogue-specific exception, not a change
to the device's advertised positive-duration lower bound.
Preparation does not establish physical acceptance or bypass confirmation on
the appliance. The runtime separately limits starts to exact catalogue defaults.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from . import zone

CATALOG_SOURCE_URL: Final = (
    "https://boraone-backend.k8s-prd.cloud.bora.com/v1/automatic-programs"
    "?pimProductId=61596&page=1&pageSize=20"
)
CATALOG_OBSERVED_DATE: Final = "2026-09-25"
PIM_PRODUCT_ID: Final = 61596
X_PURE_PRODUCT: Final = 2
FRYING_CSF_TYPE: Final = 2
UINT32_MAX: Final = 2**32 - 1
_ZERO_TIMER_PRESET_IDS: Final = frozenset({62176, 62954, 63120, 63121})


class PresetError(ValueError):
    """A preset request lacks supported metadata or contains an invalid value."""


@dataclass(frozen=True, slots=True)
class Preset:
    """Immutable facts from the observed public programme catalogue."""

    preset_id: int
    name: str
    target_celsius: int
    min_celsius: int
    max_celsius: int
    step_celsius: int


CATALOG: Final[tuple[Preset, ...]] = (
    Preset(62176, "Cook egg dishes", 135, 120, 220, 15),
    Preset(62954, "Fry potato dishes", 205, 120, 220, 15),
    Preset(63120, "Fry pancakes", 180, 120, 220, 10),
    Preset(63121, "Fry breaded foods", 170, 120, 220, 10),
)


@dataclass(frozen=True, slots=True)
class _Capabilities:
    target_min: int
    target_max: int
    step_min: int
    step_max: int
    timer_min_raw: int
    timer_max_raw: int


def _integer(value: Any, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PresetError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PresetError(f"Missing {name}")
    return value


def _bounds(value: Mapping[str, Any], low: str, high: str, name: str) -> tuple[int, int]:
    minimum = _integer(value.get(low), 0, UINT32_MAX, f"{name} minimum")
    maximum = _integer(value.get(high), minimum, UINT32_MAX, f"{name} maximum")
    return minimum, maximum


def _enum_matches(value: Any, expected: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == expected


def _contains_enum(values: Any, expected: int) -> bool:
    return isinstance(values, list | tuple) and any(
        _enum_matches(value, expected) for value in values
    )


def _matching_record(values: Any, key: str, expected: str | int, name: str) -> Mapping[str, Any]:
    if not isinstance(values, list | tuple):
        raise PresetError(f"Missing {name}")
    matches = [
        item
        for item in values
        if isinstance(item, Mapping)
        and (
            _enum_matches(item.get(key), expected)
            if isinstance(expected, int)
            else item.get(key) == expected
        )
    ]
    if len(matches) != 1:
        raise PresetError(f"A unique {name} is required")
    return matches[0]


def _capabilities(information, descriptor, uid: str) -> _Capabilities:
    information = _mapping(information, "device information")
    if not _enum_matches(information.get("product"), X_PURE_PRODUCT):
        raise PresetError("These catalogue presets are only established for X PURE product 2")
    descriptor = _mapping(descriptor, "device descriptor")
    uids = _mapping(descriptor.get("zone_uids"), "zone identities")
    if not isinstance(uid, str) or not uid or uid not in uids.values():
        raise PresetError("An advertised zone identity is required")
    zones = _mapping(descriptor.get("zone_descriptor"), "zone descriptor")
    if not _contains_enum(zones.get("zone_mode_types"), 2):
        raise PresetError("The device does not advertise CSF zone mode")
    selected_zone = _matching_record(
        zones.get("zone_mode_descriptor"), "u_id", uid, "zone CSF descriptor"
    )
    if not _contains_enum(selected_zone.get("supported_csf"), FRYING_CSF_TYPE):
        raise PresetError("The selected zone does not advertise FRYING")
    csf = _mapping(descriptor.get("csf_descriptor"), "CSF descriptor")
    frying = _matching_record(
        csf.get("type_descriptors"), "csf_type", FRYING_CSF_TYPE, "FRYING descriptor"
    )
    target = _bounds(frying, "csf_type_min_val", "csf_type_max_val", "target")
    step = _bounds(frying, "csf_type_min_step_size", "csf_type_max_step_size", "step")
    timer = _bounds(
        _mapping(csf.get("timer_limit"), "CSF timer limits"),
        "min_duration",
        "max_duration",
        "raw timer",
    )
    return _Capabilities(*target, *step, *timer)


def _recipe_supported(preset: Preset, capabilities: _Capabilities) -> bool:
    # Preserve the catalogue's range in the encoded request; never clamp it
    # silently to a different device range or invent a modulo-based step grid.
    return (
        capabilities.target_min <= preset.min_celsius
        and preset.max_celsius <= capabilities.target_max
        and capabilities.step_min <= preset.step_celsius <= capabilities.step_max
    )


def get_presets(information: Mapping, descriptor: Mapping, uid: str) -> tuple[Preset, ...]:
    """Return immutable recipes whose full target range and step are supported.

    Missing, malformed or ambiguous capabilities yield no choices. This does
    not choose a timer; prepare_preset independently validates an explicit one.
    """
    try:
        capabilities = _capabilities(information, descriptor, uid)
    except PresetError:
        return ()
    return tuple(preset for preset in CATALOG if _recipe_supported(preset, capabilities))


def reported_preset(information: Mapping, descriptor: Mapping, uid: str, status: Mapping):
    """Identify a received catalogue program without consulting a local choice."""
    if status.get("settings_present") is not True or status.get("mode") != "csf":
        return None
    parameters = (status.get("csf") or {}).get("parameters")
    if not isinstance(parameters, Mapping) or not _enum_matches(
        parameters.get("csf_type"), FRYING_CSF_TYPE
    ):
        return None
    return next(
        (
            preset for preset in get_presets(information, descriptor, uid)
            if _enum_matches(parameters.get("csf_id"), preset.preset_id)
        ),
        None,
    )


def reported_target_celsius(
    information: Mapping, descriptor: Mapping, uid: str, status: Mapping
) -> int | None:
    """Return a known recipe's reported target, never its default or a measurement."""
    preset = reported_preset(information, descriptor, uid, status)
    if preset is None:
        return None
    target = status["csf"]["parameters"].get("csf_type_target_value")
    if (
        isinstance(target, int) and not isinstance(target, bool)
        and preset.min_celsius <= target <= preset.max_celsius
    ):
        return target
    return None


def prepare_preset(
    information: Mapping,
    descriptor: Mapping,
    uid: str,
    preset_id: int,
    timer_seconds: int,
    target_celsius: int | None = None,
) -> tuple[str, bytes]:
    """Validate and encode one explicit temporary start; never transmit it.

    Positive seconds must fit the advertised raw CSF timer range after
    multiplication by 1000. Exactly the four demonstrated timerless catalogue
    starts may explicitly use zero; no timer is silently chosen by this API.
    A catalogue default such as 205 is valid without modulo checks.
    """
    preset_id = _integer(preset_id, 1, UINT32_MAX, "preset ID")
    preset = next((item for item in CATALOG if item.preset_id == preset_id), None)
    if preset is None:
        raise PresetError("Unknown catalogue preset ID")
    capabilities = _capabilities(information, descriptor, uid)
    if not _recipe_supported(preset, capabilities):
        raise PresetError("Catalogue target range or step is outside device capabilities")
    target = preset.target_celsius if target_celsius is None else target_celsius
    target = _integer(target, preset.min_celsius, preset.max_celsius, "target")
    _integer(target, capabilities.target_min, capabilities.target_max, "device target")
    seconds = _integer(timer_seconds, 0, UINT32_MAX // 1000, "timer seconds")
    if seconds == 0:
        if preset.preset_id not in _ZERO_TIMER_PRESET_IDS:
            raise PresetError("A zero timer is not established for this catalogue preset")
        timer_raw = 0
    else:
        timer_raw = _integer(
            seconds * 1000,
            capabilities.timer_min_raw,
            capabilities.timer_max_raw,
            "raw CSF timer",
        )
    return zone.start_or_modify_csf(
        uid,
        {
            "csf_id": preset.preset_id,
            "csf_index": 0,
            "csf_type": FRYING_CSF_TYPE,
            "csf_type_target_value": target,
            "csf_target_step_size": preset.step_celsius,
            "csf_target_min_val": preset.min_celsius,
            "csf_target_max_val": preset.max_celsius,
            "csf_settings": 0,
            "csf_timer_duration": timer_raw,
        },
    )
