"""The app's filter warning threshold, without invented lifetime units."""

from types import SimpleNamespace

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.bora.binary_sensor import build_entities
from custom_components.bora.ble import cooktop
from custom_components.bora.ble.wire import blob, uint


def pure_settings(remaining=0, extraction=1):
    return cooktop.decode_pure_settings(uint(7, remaining) + blob(8, uint(1, extraction)))


@pytest.mark.parametrize(
    "remaining,expected", [(0, True), (1, False), (7234, False), (0x7FFFFFFF, False)]
)
def test_app_threshold_for_normal_uint32_values(remaining, expected):
    assert cooktop.filter_change_required(pure_settings(remaining)) is expected


@pytest.mark.parametrize("remaining", [0x80000000, 0xFFFFFFFF])
def test_signed_boundary_does_not_become_a_filter_replacement_claim(remaining):
    settings = pure_settings(remaining)
    assert settings["remaining_filter_lifetime_raw"] == remaining
    assert cooktop.filter_change_required(settings) is None


@pytest.mark.parametrize("extraction", [0, 2, 99])
def test_unknown_or_outside_extraction_does_not_suggest_filter_replacement(extraction):
    assert cooktop.filter_change_required(pure_settings(0, extraction)) is None


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {"remaining_filter_lifetime_raw": 0},
        {"dealer_menu_config": {"extraction_type": 1}},
        {"dealer_menu_config": {"extraction_type": 1}, "remaining_filter_lifetime_raw": True},
    ],
)
def test_missing_or_invalid_filter_data_is_not_healthy_or_empty(settings):
    assert cooktop.filter_change_required(settings) is None


def test_explicit_pure_message_uses_protobuf_zero_default():
    # An omitted scalar in a present message is an actual protobuf default.
    # This differs from an absent entire Pure message or missing dealer mode.
    settings = cooktop.decode_pure_settings(blob(8, uint(1, 1)))
    assert cooktop.filter_change_required(settings) is True


def test_entity_follows_readback_without_controls_or_io():
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="fixture", title="BORA fixture"),
        device=SimpleNamespace(information={}, descriptor={}),
        data={"cooktop": {"cooktop_settings": {"pure": pure_settings(1)}}},
        last_update_success=True,
        controls_enabled=False,
        cooking_enabled=False,
    )
    warning = next(
        entity
        for entity in build_entities(coordinator)
        if entity.unique_id == "fixture_filter_change_required"
    )
    assert warning.available
    assert warning.is_on is False
    assert warning.device_class is BinarySensorDeviceClass.PROBLEM
    coordinator.data["cooktop"]["cooktop_settings"]["pure"] = pure_settings(0)
    assert warning.is_on is True
    coordinator.data["cooktop"]["cooktop_settings"]["pure"] = pure_settings(0, 2)
    assert warning.is_on is None
    coordinator.data["cooktop"]["cooktop_settings"]["pure"] = None
    assert not warning.available
    assert warning.is_on is None
    coordinator.data["cooktop"]["cooktop_settings"]["pure"] = pure_settings(0)
    coordinator.last_update_success = False
    assert not warning.available
