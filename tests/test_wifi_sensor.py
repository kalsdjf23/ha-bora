"""Wi-Fi display uses only an explicit snapshot and never exposes network IDs."""

from homeassistant.const import EntityCategory
from test_entities import coordinator as coordinator
from test_entities import entity_for

from custom_components.bora import sensor


def test_wifi_entity_is_optional_diagnostic_and_unknown_until_explicit_read(coordinator):
    entity = entity_for(sensor, coordinator, "wifi_status")
    assert entity.name == "Last reported Wi-Fi status"
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.entity_registry_enabled_default is False
    assert not entity.should_poll
    assert entity.device_class is None
    assert entity.native_unit_of_measurement is None
    assert not entity.available
    assert entity.native_value is None
    assert entity.extra_state_attributes is None
    coordinator.async_collect_diagnostics.assert_not_awaited()
    coordinator.async_execute.assert_not_awaited()


def test_wifi_state_preserves_distinct_labels_and_only_allowlisted_attributes(coordinator):
    entity = entity_for(sensor, coordinator, "wifi_status")
    for code, label in (
        (0, "unspecified"), (4, "wifi_connected"), (8, "no_internet"),
        (9, "internet_access"), (99, "unknown_99"),
    ):
        coordinator.device.wifi_snapshot = {
            "connection_status": code,
            "connection_status_name": label,
            "read_at": "2026-09-26T00:00:00+00:00",
            # Even an unexpectedly expanded cache must not leak these fields.
            "ssid": "PRIVATE_NETWORK", "mac_address": "aa:bb:cc:dd:ee:ff",
            "ip_v4_address": 0xC0000201, "posix_time_zone": "UTC0",
            "raw": b"private bytes",
        }
        assert entity.available
        assert entity.native_value == label
        assert entity.extra_state_attributes == {
            "connection_status": code, "last_read": "2026-09-26T00:00:00+00:00",
        }
        assert not coordinator.controls_enabled and not coordinator.cooking_enabled
    coordinator.device.wifi_snapshot = None
    assert not entity.available
    assert entity.native_value is None
    assert entity.extra_state_attributes is None
    coordinator.async_collect_diagnostics.assert_not_awaited()
    coordinator.async_execute.assert_not_awaited()


def test_main_status_failure_makes_cached_wifi_entity_unavailable(coordinator):
    coordinator.device.wifi_snapshot = {
        "connection_status": 4, "connection_status_name": "wifi_connected",
        "read_at": "2026-09-26T00:00:00+00:00",
    }
    entity = entity_for(sensor, coordinator, "wifi_status")
    assert entity.available
    coordinator.last_update_success = False
    assert not entity.available
