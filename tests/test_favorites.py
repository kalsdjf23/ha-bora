"""Saved favorites are read-only presentation, including incomplete identities."""

from copy import deepcopy

import pytest

from custom_components.bora.ble import favorites, identify, presets
from custom_components.bora.ble.wire import blob, uint


def descriptor(minimum=1, maximum=5):
    return {"csf_descriptor": {"index_range": {"min": minimum, "max": maximum}}}


@pytest.mark.parametrize("bounds", [(1, 5), (3, 5), (0, 10), (0, 2**32 - 1)])
def test_supports_advertised_app_slots(bounds):
    assert favorites.supports_favorites({"product": 2}, descriptor(*bounds))


@pytest.mark.parametrize("product", [None, True, False, 0, 1, 3, 4, "2", 2.0])
def test_support_requires_exact_product(product):
    assert not favorites.supports_favorites({"product": product}, descriptor())


@pytest.mark.parametrize(
    "bounds",
    [(4, 5), (1, 4), (5, 3), (-1, 5), (0, 2**32), (True, 5), (1, True),
     (None, 5), (1, None), ("1", 5), (1, "5"), (1.0, 5), (1, 5.0)],
)
def test_support_rejects_incomplete_or_invalid_index_range(bounds):
    assert not favorites.supports_favorites({"product": 2}, descriptor(*bounds))


@pytest.mark.parametrize(
    "metadata",
    [None, [], {}, {"csf_descriptor": None}, {"csf_descriptor": []},
     {"csf_descriptor": {}}, {"csf_descriptor": {"index_range": None}},
     {"csf_descriptor": {"index_range": []}},
     {"csf_descriptor": {"index_range": {"max": 5}}},
     {"csf_descriptor": {"index_range": {"min": 1}}}],
)
def test_support_rejects_missing_descriptor(metadata):
    assert not favorites.supports_favorites({"product": 2}, metadata)


@pytest.mark.parametrize("information", [None, [], {}, "product2"])
def test_support_handles_missing_information(information):
    assert not favorites.supports_favorites(information, descriptor())


def test_support_does_not_require_known_recipe_or_control_capabilities():
    # Presentation of an unknown type does not grant control of that type.
    assert favorites.supports_favorites({"product": 2}, descriptor())


def test_empty_response_describes_all_three_slots():
    assert favorites.describe_favorites(identify.decode_saved_csf(b"")) == {
        slot: {"state": "empty", "label": "empty", "parameters": None, "candidates": []}
        for slot in (3, 4, 5)
    }


@pytest.mark.parametrize("preset", presets.CATALOG)
def test_known_label_uses_decoded_id_and_type_without_parameter_defaults(preset):
    # Actual read values deliberately differ from catalogue defaults. No units
    # or validity are inferred just because the identity has a known label.
    raw = (
        uint(1, preset.preset_id) + uint(3, 4) + uint(4, 2)
        + uint(5, 0) + uint(10, 128) + uint(11, 12345)
    )
    decoded = identify.decode_saved_csf(blob(1, raw))
    record = favorites.describe_favorites(decoded)[4]
    assert record == {
        "state": "known", "label": preset.name, "parameters": decoded[0], "candidates": []
    }
    assert record["parameters"] is not decoded[0]
    assert record["parameters"]["csf_type_target_value"] == 0
    assert record["parameters"]["csf_timer_duration"] == 12345
    assert record["parameters"]["csf_settings"] == 128


@pytest.mark.parametrize("preset_id", [0, 1, 5, 99999, 2**32 - 1])
@pytest.mark.parametrize("csf_type", [0, 1, 2, 3, 42])
def test_unknown_ids_and_types_remain_visible(preset_id, csf_type):
    parameters = identify.decode_saved_csf(
        blob(1, uint(1, preset_id) + uint(3, 3) + uint(4, csf_type))
    )
    record = favorites.describe_favorites(parameters)[3]
    assert record["state"] == "unknown"
    assert record["label"] == f"unknown_{preset_id}"
    assert record["parameters"] == parameters[0]


@pytest.mark.parametrize("csf_type", [None, 0, 1, 3, 42, True, "2", 2.0, []])
def test_known_id_with_other_type_never_gets_recipe_label(csf_type):
    record = favorites.describe_favorites(
        [{"csf_index": 5, "csf_id": 62176, "csf_type": csf_type}]
    )[5]
    assert record["state"] == "unknown"
    assert record["label"] == "unknown_62176"
    assert record["parameters"]["csf_type"] == csf_type


@pytest.mark.parametrize("preset_id", [None, True, "62176", 62176.0, [], {}])
def test_malformed_id_is_visible_without_fabricating_an_id(preset_id):
    record = favorites.describe_favorites(
        [{"csf_index": 3, "csf_id": preset_id, "csf_type": 2}]
    )[3]
    assert record["state"] == "unknown"
    assert record["label"] == "unknown"
    assert record["parameters"]["csf_id"] == preset_id


@pytest.mark.parametrize("slot", [3, 4, 5])
@pytest.mark.parametrize("second_id", [62176, 62954, 99999])
def test_duplicate_indices_are_ambiguous_even_for_identical_records(slot, second_id):
    parameters = [
        {"csf_index": slot, "csf_id": 62176, "csf_type": 2},
        {"csf_index": slot, "csf_id": second_id, "csf_type": 2},
    ]
    result = favorites.describe_favorites(parameters)
    assert result[slot] == {
        "state": "ambiguous", "label": "ambiguous",
        "parameters": None, "candidates": parameters,
    }
    assert all(result[other]["state"] == "empty" for other in (3, 4, 5) if other != slot)


def test_unrelated_or_malformed_slots_do_not_shadow_app_slots():
    parameters = [
        {"csf_index": slot, "csf_id": 62176, "csf_type": 2}
        for slot in (0, 1, 2, 6, 99, None, True, "3", 3.0)
    ]
    parameters.extend([{}, None])
    parameters.append({"csf_index": 3, "csf_id": 62176, "csf_type": 2})
    result = favorites.describe_favorites(parameters)
    assert list(result) == [3, 4, 5]
    assert result[3]["state"] == "known"
    assert result[4]["state"] == result[5]["state"] == "empty"


@pytest.mark.parametrize("duplicate", [False, True])
def test_results_deep_copy_raw_parameters_and_preserve_presence(duplicate):
    raw = {
        "csf_index": 3, "csf_id": 62176, "csf_type": 2,
        "csf_time_to_set_obsolete": {"duration": 123},
        "csf_timer_duration": 456, "present_fields": (1, 3, 4, 6, 11),
        "future_extension": {"payload": b"\xff", "values": [1, {"flag": 2}]},
    }
    parameters = [raw, raw] if duplicate else [raw]
    before = deepcopy(parameters)
    record = favorites.describe_favorites(parameters)[3]
    assert parameters == before
    copies = record["candidates"] if duplicate else [record["parameters"]]
    assert copies == before
    raw["csf_time_to_set_obsolete"]["duration"] = 900
    assert copies[0]["csf_time_to_set_obsolete"]["duration"] == 123
    copies[0]["future_extension"]["values"][1]["flag"] = 7
    assert raw["future_extension"]["values"][1]["flag"] == 2
    if duplicate:
        assert copies[1]["future_extension"]["values"][1]["flag"] == 2


def test_response_order_does_not_change_unique_slot_mapping():
    parameters = [
        {"csf_index": 5, "csf_id": 63120, "csf_type": 2},
        {"csf_index": 3, "csf_id": 62176, "csf_type": 2},
        {"csf_index": 4, "csf_id": 42, "csf_type": 99},
    ]
    assert favorites.describe_favorites(parameters) == favorites.describe_favorites(
        list(reversed(parameters))
    )
