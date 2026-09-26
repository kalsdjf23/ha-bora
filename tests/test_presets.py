"""Pure preset preparation against independent factual and recorded fixtures."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pytest

from custom_components.bora.ble import identify, presets, zone
from custom_components.bora.ble.wire import FrameDecoder, Message, Response, uint

UID = "front_left"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def catalog():
    return json.loads((FIXTURES / "x_pure_catalogue_2026_09_25.json").read_text())


@pytest.fixture
def information():
    return identify.decode_information(uint(1, 2))


@pytest.fixture
def descriptor():
    fixture = json.loads((FIXTURES / "x_pure_3_0_9.json").read_text())
    session = next(item for item in fixture["sessions"] if item["name"] == "device-descriptor-1")
    decoder = FrameDecoder()
    bodies = [
        Response.decode(frame).body
        for event in session["events"]
        if event["event"] == "notification"
        for frame in decoder.feed(bytes.fromhex(event["hex"]))
    ]
    assert len(bodies) == 1
    return identify.decode_descriptor(bodies[0])


def parameter(command):
    path, body = command
    assert path == zone.SERVICE_PATH + "StartOrModifyCsf"
    request = Message(body)
    assert request.text(2) == UID
    return zone.decode_csf_parameter(request.bytes(1))


def frying_descriptor(descriptor):
    return next(
        item for item in descriptor["csf_descriptor"]["type_descriptors"] if item["csf_type"] == 2
    )


def replace_field(mapping, path, value):
    parent = mapping
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value


def test_immutable_catalogue_matches_independent_public_response(catalog, information, descriptor):
    assert presets.CATALOG_SOURCE_URL == catalog["source_url"]
    assert presets.CATALOG_OBSERVED_DATE == catalog["observed_date"]
    assert len(presets.CATALOG) == catalog["pagination"]["totalCount"] == 4
    expected = []
    for record in catalog["programs"]:
        assert record["deviceType"] == presets.PIM_PRODUCT_ID
        step, = record["programSteps"]
        assert step["cookingMethodKey"] == "FRYING"
        assert step["cooktopTimer"] is True
        expected.append(
            {
                "preset_id": record["id"],
                "name": record["title"],
                "target_celsius": int(step["temperatureCvValue"].removesuffix(" °C")),
                "min_celsius": step["minControlSize"],
                "max_celsius": step["maxControlSize"],
                "step_celsius": step["controlStepSize"],
            }
        )
    assert [asdict(item) for item in presets.CATALOG] == expected
    choices = presets.get_presets(information, descriptor, UID)
    assert choices == presets.CATALOG
    assert isinstance(choices, tuple)
    with pytest.raises(FrozenInstanceError):
        choices[0].target_celsius = 999


def test_all_catalogue_defaults_encode_explicit_temporary_starts(catalog, information, descriptor):
    for record in catalog["programs"]:
        step, = record["programSteps"]
        result = parameter(
            presets.prepare_preset(information, descriptor, UID, record["id"], timer_seconds=30)
        )
        assert result["csf_id"] == record["id"]
        assert result["csf_index"] == 0  # Temporary app start, not saved-slot range 1..5.
        assert result["csf_type"] == 2
        expected_target = int(step["temperatureCvValue"].removesuffix(" °C"))
        assert result["csf_type_target_value"] == expected_target
        assert result["csf_target_step_size"] == step["controlStepSize"]
        assert result["csf_target_min_val"] == step["minControlSize"]
        assert result["csf_target_max_val"] == step["maxControlSize"]
        assert result["csf_settings"] == 0
        assert result["csf_timer_duration"] == 30000
        assert result["present_fields"] == (1, 3, 4, 5, 7, 8, 9, 10, 11)


def test_catalogue_205_default_is_not_rejected_by_an_invented_modulo_grid(information, descriptor):
    result = parameter(presets.prepare_preset(information, descriptor, UID, 62954, 30))
    assert result["csf_type_target_value"] == 205
    assert (205 - result["csf_target_min_val"]) % result["csf_target_step_size"] != 0


@pytest.mark.parametrize("target", [120, 205, 220])
def test_explicit_target_is_kept_within_catalogue_and_device_bounds(
    information, descriptor, target
):
    result = parameter(presets.prepare_preset(information, descriptor, UID, 62176, 30, target))
    assert result["csf_type_target_value"] == target


@pytest.mark.parametrize("target", [119, 221, True, 135.0, "135", -1])
def test_invalid_target_is_rejected_even_when_device_range_is_wider(
    information, descriptor, target
):
    assert frying_descriptor(descriptor)["csf_type_max_val"] == 240
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30, target)


def test_zero_timer_is_exact_catalogue_exception_not_new_positive_lower_bound(
    catalog, information, descriptor
):
    limits = descriptor["csf_descriptor"]["timer_limit"]
    assert limits["min_duration"] == 10000
    for record in catalog["programs"]:
        result = parameter(presets.prepare_preset(information, descriptor, UID, record["id"], 0))
        assert result["csf_timer_duration"] == 0
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 99999, 0)
    for positive_below_minimum in (1, 9):
        with pytest.raises(presets.PresetError):
            presets.prepare_preset(information, descriptor, UID, 62176, positive_below_minimum)
    assert limits["min_duration"] == 10000


def test_new_catalogue_entry_does_not_inherit_zero_exception(information, descriptor, monkeypatch):
    future = presets.Preset(99999, "Synthetic future preset", 135, 120, 220, 15)
    monkeypatch.setattr(presets, "CATALOG", (*presets.CATALOG, future))
    descriptor["csf_descriptor"]["timer_limit"]["min_duration"] = 0
    with pytest.raises(presets.PresetError, match="zero timer is not established"):
        presets.prepare_preset(information, descriptor, UID, future.preset_id, 0)


@pytest.mark.parametrize(("seconds", "milliseconds"), [(10, 10000), (7250, 7250000)])
def test_positive_timer_boundaries_compare_converted_raw_value(
    information, descriptor, seconds, milliseconds
):
    result = parameter(presets.prepare_preset(information, descriptor, UID, 62176, seconds))
    assert result["csf_timer_duration"] == milliseconds


@pytest.mark.parametrize("seconds", [-1, 7251, True, False, 30.0, "30", None, 4294968])
def test_invalid_timer_is_never_coerced_or_defaulted(information, descriptor, seconds):
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, seconds)


def test_timer_argument_is_required(information, descriptor):
    with pytest.raises(TypeError):
        presets.prepare_preset(information, descriptor, UID, 62176)


@pytest.mark.parametrize("preset_id", [True, 62176.0, "62176", 0, -1, 99999, None])
def test_unknown_or_noninteger_catalogue_id_is_rejected(information, descriptor, preset_id):
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, preset_id, 30)


@pytest.mark.parametrize(
    "information",
    [None, {}, {"product_name": "x_pure"}, {"product": 1}, {"product": 6}, {"product": 2.0}],
)
def test_product_must_be_the_known_x_pure_enum(information, descriptor):
    assert presets.get_presets(information, descriptor, UID) == ()
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30)


@pytest.mark.parametrize("uid", ["unknown", "", None, True])
def test_zone_must_be_explicitly_advertised(information, descriptor, uid):
    assert presets.get_presets(information, descriptor, uid) == ()
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, uid, 62176, 30)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("zone_uids",), None),
        (("zone_descriptor",), None),
        (("zone_descriptor", "zone_mode_types"), [1, 3, 4]),
        (("zone_descriptor", "zone_mode_types"), [2.0]),
        (("zone_descriptor", "zone_mode_descriptor"), []),
        (("csf_descriptor",), None),
        (("csf_descriptor", "type_descriptors"), []),
        (("csf_descriptor", "timer_limit"), None),
        (("csf_descriptor", "timer_limit", "min_duration"), True),
        (("csf_descriptor", "timer_limit", "max_duration"), 9999),
    ],
)
def test_missing_or_invalid_capability_never_offers_a_preset(information, descriptor, path, value):
    replace_field(descriptor, path, value)
    assert presets.get_presets(information, descriptor, UID) == ()
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30)


def test_global_frying_support_does_not_replace_per_zone_support(information, descriptor):
    zones = descriptor["zone_descriptor"]["zone_mode_descriptor"]
    target = next(item for item in zones if item["u_id"] == UID)
    target["supported_csf"] = [1, 3, 4, 5]
    assert presets.get_presets(information, descriptor, UID) == ()
    assert len(presets.get_presets(information, descriptor, "back_right")) == 4
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30)


@pytest.mark.parametrize(("minimum", "maximum", "steps"), [(1, 12, {10}), (11, 20, {15})])
def test_device_step_bounds_filter_catalogue_without_modulo_rules(
    information, descriptor, minimum, maximum, steps
):
    frying = frying_descriptor(descriptor)
    frying["csf_type_min_step_size"] = minimum
    frying["csf_type_max_step_size"] = maximum
    choices = presets.get_presets(information, descriptor, UID)
    assert len(choices) == 2
    assert {item.step_celsius for item in choices} == steps
    for preset in presets.CATALOG:
        if preset.step_celsius not in steps:
            with pytest.raises(presets.PresetError):
                presets.prepare_preset(information, descriptor, UID, preset.preset_id, 30)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("csf_type_min_val", 121),
        ("csf_type_max_val", 219),
        ("csf_type_min_val", True),
        ("csf_type_max_val", 240.0),
        ("csf_type_min_step_size", "1"),
        ("csf_type_max_step_size", None),
        ("csf_type_max_step_size", 0),
    ],
)
def test_recipe_range_and_step_are_not_clamped_to_incompatible_descriptors(
    information, descriptor, field, value
):
    frying_descriptor(descriptor)[field] = value
    assert presets.get_presets(information, descriptor, UID) == ()
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30, target_celsius=180)


@pytest.mark.parametrize("duplicate", ["zone", "frying"])
def test_ambiguous_descriptor_entries_are_rejected(information, descriptor, duplicate):
    if duplicate == "zone":
        records = descriptor["zone_descriptor"]["zone_mode_descriptor"]
        records.append(deepcopy(next(item for item in records if item["u_id"] == UID)))
    else:
        descriptor["csf_descriptor"]["type_descriptors"].append(deepcopy(frying_descriptor(descriptor)))
    assert presets.get_presets(information, descriptor, UID) == ()
    with pytest.raises(presets.PresetError):
        presets.prepare_preset(information, descriptor, UID, 62176, 30)


def test_preparation_does_not_mutate_metadata_or_descriptor(information, descriptor):
    original_info, original_descriptor = deepcopy(information), deepcopy(descriptor)
    presets.get_presets(information, descriptor, UID)
    presets.prepare_preset(information, descriptor, UID, 62176, 30, 200)
    assert information == original_info
    assert descriptor == original_descriptor
    assert presets.CATALOG[0].target_celsius == 135
