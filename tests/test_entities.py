"""Entity behavior against recorded snapshots and a mocked coordinator only."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.exceptions import HomeAssistantError

from custom_components.bora import binary_sensor, button, fan, number, select, sensor, switch
from custom_components.bora.ble import cooktop, extractor, identify, zone
from custom_components.bora.ble.wire import FrameDecoder, Response, uint

PLATFORMS = (sensor, binary_sensor, fan, number, select, switch, button)


def recorded_bodies():
    recorded = json.loads((Path(__file__).parent / "fixtures/x_pure_3_0_9.json").read_text())
    bodies = {}
    for session in recorded["sessions"]:
        decoder = FrameDecoder()
        for event in session["events"]:
            if event["event"] != "notification":
                continue
            for payload in decoder.feed(bytes.fromhex(event["hex"])):
                response = Response.decode(payload)
                if response.body is not None:
                    bodies[session["name"]] = response.body
    return bodies


@pytest.fixture
def coordinator():
    bodies = recorded_bodies()
    zones = {
        status["uid"]: status
        for name, body in bodies.items()
        if name.startswith("zone-status-")
        for status in [zone.decode_status(body)]
    }
    entry = SimpleNamespace(entry_id="test_entry", title="Test BORA")
    result = SimpleNamespace(
        entry=entry,
        device=SimpleNamespace(
            information={"product_name": "x_pure", "cm_sw_version_no": "3.0.9"},
            descriptor=identify.decode_descriptor(bodies["device-descriptor-1"]),
        ),
        data={
            "extractor": extractor.decode_status(bodies["status-request-3"]),
            "cooktop": cooktop.decode_status(bodies["cooktop-status-1"]),
            "zones": zones,
        },
        last_update_success=True,
        controls_enabled=False,
        cooking_enabled=False,
        async_execute=AsyncMock(),
        async_set_simple_function=AsyncMock(),
        async_collect_diagnostics=AsyncMock(),
    )
    entry.runtime_data = result
    return result


def entity_for(module, coordinator, key):
    identity = getattr(coordinator.entry, "unique_id", None) or coordinator.entry.entry_id
    return next(
        entity
        for entity in module.build_entities(coordinator)
        if entity.unique_id == identity + "_" + key
    )


def unlock(coordinator):
    coordinator.controls_enabled = True
    coordinator.cooking_enabled = True


def test_recorded_readings_do_not_depend_on_enabled_controls(coordinator):
    level = entity_for(sensor, coordinator, "extractor_level")
    assert level.available
    assert level.native_value == 1
    assert level.extra_state_attributes["level_label"] == "1"
    assert entity_for(sensor, coordinator, "after_run_remaining").native_value == 1754
    assert entity_for(sensor, coordinator, "configured_after_run").native_value == 30
    assert entity_for(sensor, coordinator, "front_left_power").native_value == 0
    assert entity_for(binary_sensor, coordinator, "front_left_residual_heat").is_on is False
    assert entity_for(binary_sensor, coordinator, "front_left_pot_detection").is_on is True
    assert entity_for(binary_sensor, coordinator, "front_left_pot_detection").device_class is None
    assert level.device_info["identifiers"] == {("bora", "test_entry")}
    assert level.device_info["manufacturer"] == "BORA"


def test_unverified_filter_and_egg_timer_units_remain_raw_attributes(coordinator):
    power = entity_for(sensor, coordinator, "front_left_power")
    assert power.native_unit_of_measurement is None
    assert power.extra_state_attributes["timer_raw"]["duration"] == 0
    connectivity = entity_for(sensor, coordinator, "connectivity")
    assert "remaining_filter_lifetime_raw" in connectivity.extra_state_attributes
    extractor_level = entity_for(sensor, coordinator, "extractor_level")
    assert "egg_timer_raw" in extractor_level.extra_state_attributes
    assert not any(
        "egg_timer" in entity.unique_id or "filter" in entity.unique_id
        for entity in sensor.build_entities(coordinator)
    )


def test_zone_timer_milliseconds_are_readable_with_controls_disabled(coordinator):
    timer = zone.decode_timer(uint(1, 33000) + uint(2, 33000) + uint(3, 1))
    coordinator.data["zones"]["front_left"]["timer"] = timer
    assert not coordinator.controls_enabled
    assert not coordinator.cooking_enabled
    for field in ("duration", "remaining"):
        entity = entity_for(sensor, coordinator, f"front_left_timer_{field}")
        assert entity.available
        assert entity.native_value == 33
        assert entity.native_unit_of_measurement is UnitOfTime.SECONDS
        assert entity.device_class is SensorDeviceClass.DURATION
        assert entity.extra_state_attributes == {"timer_raw": timer}
    running = entity_for(binary_sensor, coordinator, "front_left_timer_running")
    assert running.available
    assert running.is_on is True
    coordinator.async_execute.assert_not_awaited()


def test_timer_entities_follow_their_own_zone_and_preserve_fractional_seconds(coordinator):
    for index, uid in enumerate(coordinator.data["zones"], start=1):
        coordinator.data["zones"][uid]["timer"] = zone.decode_timer(
            uint(1, index * 33000) + uint(2, index * 1500) + uint(3, index % 2)
        )
    sensors = {entity.unique_id: entity for entity in sensor.build_entities(coordinator)}
    booleans = {entity.unique_id: entity for entity in binary_sensor.build_entities(coordinator)}
    for index, uid in enumerate(coordinator.data["zones"], start=1):
        assert sensors[f"test_entry_{uid}_timer_duration"].native_value == index * 33
        assert sensors[f"test_entry_{uid}_timer_remaining"].native_value == index * 1.5
        assert booleans[f"test_entry_{uid}_timer_running"].is_on is bool(index % 2)


@pytest.mark.parametrize("remove_field", [False, True])
def test_missing_timer_is_unavailable_and_can_recover_without_recreating_entities(
    coordinator, remove_field
):
    status = coordinator.data["zones"]["front_left"]
    if remove_field:
        status.pop("timer")
    else:
        status["timer"] = None
    duration = entity_for(sensor, coordinator, "front_left_timer_duration")
    remaining = entity_for(sensor, coordinator, "front_left_timer_remaining")
    running = entity_for(binary_sensor, coordinator, "front_left_timer_running")
    for entity in (duration, remaining, running):
        assert not entity.available
    assert duration.native_value is None
    assert remaining.native_value is None
    assert duration.extra_state_attributes is None
    assert running.is_on is None

    # An explicitly present empty protobuf timer supplies genuine zero/false defaults.
    status["timer"] = zone.decode_timer(b"")
    for entity in (duration, remaining, running):
        assert entity.available
    assert duration.native_value == 0
    assert remaining.native_value == 0
    assert running.is_on is False

    status["timer"] = None
    assert not running.available
    assert running.is_on is None
    assert not remaining.available
    assert remaining.native_value is None


def test_missing_snapshots_stay_unknown(coordinator):
    entities = [entity for module in PLATFORMS for entity in module.build_entities(coordinator)]
    coordinator.data = {"extractor": None, "cooktop": None, "zones": {}}
    for entity in entities:
        if isinstance(entity, button.BoraDiagnosticsButton):
            continue  # Optional read-only diagnostics can still be requested.
        assert not entity.available
        if isinstance(entity, sensor.BoraSensor | number.BoraZonePower):
            assert entity.native_value is None
        elif isinstance(
            entity,
            binary_sensor.BoraBinarySensor | switch.BoraSwitch | switch.BoraSimpleFunctionSwitch,
        ):
            assert entity.is_on is None
        elif isinstance(entity, select.BoraSelect):
            assert entity.current_option is None
        elif isinstance(entity, fan.BoraExtractorFan):
            assert entity.is_on is None
            assert entity.percentage is None


@pytest.mark.parametrize("platform", PLATFORMS)
async def test_platform_setup_uses_entry_runtime_data(coordinator, platform):
    added = []
    await platform.async_setup_entry(None, coordinator.entry, added.extend)
    assert added
    assert all(entity.coordinator is coordinator for entity in added)
    assert len({entity.unique_id for entity in added}) == len(added)


@pytest.mark.parametrize(
    ("module", "key", "method", "args"),
    [
        (fan, "extractor", "async_set_percentage", (50,)),
        (fan, "extractor", "async_set_preset_mode", ("auto",)),
        (number, "front_left_set_power", "async_set_native_value", (3,)),
        (select, "signal_volume", "async_select_option", ("22%",)),
        (select, "front_left_keep_warm", "async_select_option", ("keep_warm",)),
        (switch, "set_paused", "async_turn_off", ()),
        (switch, "set_clean_lock", "async_turn_on", ()),
        (switch, "simple_warming_disabled", "async_turn_on", ()),
        (button, "stop_after_run", "async_press", ()),
    ],
)
async def test_every_control_enforces_disabled_options(coordinator, module, key, method, args):
    entity = entity_for(module, coordinator, key)
    assert not entity.available
    with pytest.raises(HomeAssistantError):
        await getattr(entity, method)(*args)
    coordinator.async_execute.assert_not_awaited()
    coordinator.async_set_simple_function.assert_not_awaited()


async def test_cooking_guard_is_separate_from_general_controls(coordinator):
    coordinator.controls_enabled = True
    assert entity_for(fan, coordinator, "extractor").available
    power = entity_for(number, coordinator, "front_left_set_power")
    assert not power.available
    with pytest.raises(HomeAssistantError):
        await power.async_set_native_value(3)
    coordinator.cooking_enabled = True
    assert power.available
    await power.async_set_native_value(3)
    command = coordinator.async_execute.call_args.args[0]
    assert command == zone.set_power("front_left", 3)
    assert coordinator.async_execute.call_args.kwargs == {"cooking": True}


async def test_offline_coordinator_blocks_control_even_when_options_enabled(coordinator):
    unlock(coordinator)
    entity = entity_for(fan, coordinator, "extractor")
    coordinator.last_update_success = False
    assert not entity.available
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()
    coordinator.async_execute.assert_not_awaited()


async def test_fan_manual_percent_auto_and_boost_use_descriptor(coordinator):
    unlock(coordinator)
    entity = entity_for(fan, coordinator, "extractor")
    assert entity.preset_modes == ["auto", "P"]
    assert entity.speed_count == 8
    await entity.async_set_percentage(100)
    assert coordinator.async_execute.call_args.args[0] == extractor.set_power_level(8)
    await entity.async_set_preset_mode("P")
    assert coordinator.async_execute.call_args.args[0] == extractor.set_power_level(9)
    await entity.async_set_preset_mode("auto")
    assert coordinator.async_execute.call_args.args[0] == extractor.set_auto_mode()
    await entity.async_turn_off()
    assert coordinator.async_execute.call_args.args[0] == extractor.set_power_level(0)
    coordinator.data["extractor"]["extractor_settings"]["extractor_mode"] = {
        "mode": "power_level",
        "power_level": 3,
    }
    assert entity.percentage == 37
    await entity.async_turn_on()
    assert coordinator.async_execute.call_args.args[0] == extractor.set_power_level(3)


async def test_fan_missing_mode_and_unadvertised_presets(coordinator):
    unlock(coordinator)
    entity = entity_for(fan, coordinator, "extractor")
    coordinator.data["extractor"]["extractor_settings"]["extractor_mode"] = None
    assert entity.percentage is None
    assert entity.is_on is None
    for value in ("boost", "invalid"):
        with pytest.raises(HomeAssistantError):
            await entity.async_set_preset_mode(value)
    for value in (-1, 101, float("nan"), True):
        with pytest.raises(HomeAssistantError):
            await entity.async_set_percentage(value)
    coordinator.async_execute.assert_not_awaited()


async def test_power_range_and_boost_label_are_dynamic(coordinator):
    unlock(coordinator)
    power = entity_for(number, coordinator, "front_left_set_power")
    assert (power.native_min_value, power.native_max_value) == (0, 10)
    assert power.extra_state_attributes["level_labels"][10] == "P"
    await power.async_set_native_value(10.0)
    assert coordinator.async_execute.call_args.args[0] == zone.set_power("front_left", 10)
    for value in (11, -1, 2.5, True, float("inf"), float("nan")):
        with pytest.raises((HomeAssistantError, ValueError)):
            await power.async_set_native_value(value)


async def test_sparse_levels_use_select_without_inventing_intermediate_choices(coordinator):
    unlock(coordinator)
    coordinator.device.descriptor["zone_descriptor"]["power_levels"] = [
        {"index": 0, "level_name": "off"},
        {"index": 2, "level_name": "normal"},
        {"index": 8, "level_name": "P"},
    ]
    assert number.build_entities(coordinator) == []
    selected = entity_for(select, coordinator, "front_left_set_power")
    assert selected.options == ["off", "normal", "P"]
    await selected.async_select_option("normal")
    assert coordinator.async_execute.call_args.args[0] == zone.set_power("front_left", 2)


async def test_after_run_current_unadvertised_value_is_readable_but_not_selectable(coordinator):
    unlock(coordinator)
    selected = entity_for(select, coordinator, "after_run_duration")
    assert selected.options == ["10 min", "15 min", "20 min"]
    assert selected.current_option is None
    assert entity_for(sensor, coordinator, "configured_after_run").native_value == 30
    with pytest.raises(HomeAssistantError):
        await selected.async_select_option("30 min")
    await selected.async_select_option("15 min")
    assert coordinator.async_execute.call_args.args[0] == extractor.set_after_run_duration(2)


async def test_pure_controls_require_live_pure_snapshot(coordinator):
    unlock(coordinator)
    sensitivity = entity_for(select, coordinator, "sensitivity")
    retention = entity_for(select, coordinator, "front_left_keep_warm")
    coordinator.data["cooktop"]["cooktop_settings"]["pure"] = None
    assert not sensitivity.available
    assert not retention.available
    with pytest.raises(HomeAssistantError):
        await retention.async_select_option("keep_warm")
    keys = {entity.unique_id for entity in select.build_entities(coordinator)}
    assert "test_entry_sensitivity" not in keys
    assert "test_entry_front_left_keep_warm" not in keys
    coordinator.async_execute.assert_not_awaited()


async def test_pure_mode_controls_encode_nested_settings_and_correct_zone(coordinator):
    unlock(coordinator)
    await entity_for(select, coordinator, "back_right_keep_warm").async_select_option("simmering")
    assert coordinator.async_execute.call_args.args[0] == zone.set_keep_warm("back_right", 3)
    await entity_for(select, coordinator, "front_left_heat_up").async_select_option("4")
    assert coordinator.async_execute.call_args.args[0] == zone.set_heat_up("front_left", 4)
    await entity_for(select, coordinator, "sensitivity").async_select_option("slow")
    assert coordinator.async_execute.call_args.args[0] == cooktop.set_touch_sensitivity(1)


async def test_simple_mode_sends_intent_to_atomic_coordinator_path(coordinator):
    unlock(coordinator)
    pure = coordinator.data["cooktop"]["cooktop_settings"]["pure"]
    pure["super_simple_mode"]["disabled_functions"] = {
        "cleaning_lock_disabled": True,
        "pause_disabled": False,
        "warming_disabled": True,
        "timer_disabled": False,
        "hot_key_disabled": True,
    }
    entity = entity_for(switch, coordinator, "simple_warming_disabled")
    assert entity.is_on is False
    await entity.async_turn_on()
    coordinator.async_set_simple_function.assert_awaited_once_with("warming_disabled", True)
    coordinator.async_execute.assert_not_awaited()
    assert pure["super_simple_mode"]["disabled_functions"]["warming_disabled"] is True
    await entity.async_turn_off()
    assert coordinator.async_set_simple_function.call_args.args == ("warming_disabled", False)
    pure["super_simple_mode"]["disabled_functions"] = None
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()


async def test_simple_mode_keeps_separate_cooking_guard(coordinator):
    coordinator.controls_enabled = True
    entity = entity_for(switch, coordinator, "simple_warming_disabled")
    assert not entity.available
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()
    coordinator.async_set_simple_function.assert_not_awaited()


async def test_diagnostics_refresh_works_in_monitoring_mode(coordinator):
    entity = entity_for(button, coordinator, "refresh_diagnostics")
    assert not coordinator.controls_enabled
    assert not coordinator.cooking_enabled
    assert entity.available
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.entity_registry_enabled_default is False
    await entity.async_press()
    coordinator.async_collect_diagnostics.assert_awaited_once_with()
    coordinator.async_execute.assert_not_awaited()


async def test_diagnostics_refresh_respects_connection_availability(coordinator):
    entity = entity_for(button, coordinator, "refresh_diagnostics")
    coordinator.last_update_success = False
    assert not entity.available
    with pytest.raises(HomeAssistantError):
        await entity.async_press()
    coordinator.async_collect_diagnostics.assert_not_awaited()


def test_bluetooth_identity_survives_config_entry_recreation(coordinator):
    coordinator.entry.unique_id = "AA:BB:CC:DD:EE:FF"
    original = entity_for(sensor, coordinator, "extractor_level")
    coordinator.entry.entry_id = "replacement_entry"
    replacement = entity_for(sensor, coordinator, "extractor_level")
    assert original.unique_id == replacement.unique_id == "AA:BB:CC:DD:EE:FF_extractor_level"
    assert (
        original.device_info["identifiers"]
        == replacement.device_info["identifiers"]
        == {("bora", "AA:BB:CC:DD:EE:FF")}
    )


async def test_stop_actions_only_available_for_active_state(coordinator):
    unlock(coordinator)
    after_run = entity_for(button, coordinator, "stop_after_run")
    assert after_run.available
    await after_run.async_press()
    assert coordinator.async_execute.call_args.args[0] == extractor.stop_after_run()
    coordinator.data["extractor"]["remaining_after_run_ms"] = 0
    assert not after_run.available
    csf_stop = entity_for(button, coordinator, "front_left_stop_csf")
    assert not csf_stop.available
    coordinator.data["zones"]["front_left"].update(mode="csf", csf={"phase": 3})
    assert csf_stop.available
    await csf_stop.async_press()
    assert coordinator.async_execute.call_args.args[0] == zone.stop_csf("front_left")
    assert coordinator.async_execute.call_args.kwargs == {"cooking": True}


def test_descriptor_capabilities_gate_zone_controls(coordinator):
    coordinator.device.descriptor["zone_descriptor"]["zone_mode_types"] = []
    assert number.build_entities(coordinator) == []
    assert not any(
        "front_left" in entity.unique_id for entity in select.build_entities(coordinator)
    )
    assert not any("csf" in entity.unique_id for entity in button.build_entities(coordinator))
    coordinator.device.descriptor["zone_uids"] = None
    assert not any(
        "front_left" in entity.unique_id for entity in sensor.build_entities(coordinator)
    )


async def test_auto_only_fan_never_defaults_to_a_manual_write(coordinator):
    unlock(coordinator)
    coordinator.device.descriptor["extractor_descriptor"]["extractor_mode_types"] = [1]
    entity = entity_for(fan, coordinator, "extractor")
    assert entity.preset_modes == ["auto"]
    await entity.async_turn_on()
    assert coordinator.async_execute.call_args.args[0] == extractor.set_auto_mode()
    with pytest.raises(HomeAssistantError):
        await entity.async_set_percentage(50)


def test_removed_capabilities_disable_existing_entities(coordinator):
    unlock(coordinator)
    entities = [
        entity_for(fan, coordinator, "extractor"),
        entity_for(number, coordinator, "front_left_set_power"),
        entity_for(select, coordinator, "front_left_keep_warm"),
        entity_for(select, coordinator, "front_left_heat_up"),
        entity_for(select, coordinator, "signal_volume"),
    ]
    coordinator.device.descriptor = {}
    assert all(not entity.available for entity in entities)
    assert fan.build_entities(coordinator) == []


def test_error_labels_preserve_unknown_codes_without_diagnosing_cause(coordinator):
    coordinator.data["cooktop"]["current_primary_device_errors"] = [11, 999]
    errors = entity_for(sensor, coordinator, "errors")
    assert errors.native_value == 2
    assert errors.extra_state_attributes["codes"] == [11, 999]
    assert errors.extra_state_attributes["labels"] == ["H_LEFT_FRONT", "unknown_999"]


def test_no_forbidden_controls_or_unverified_egg_timer_controls(coordinator):
    entities = [entity for module in PLATFORMS for entity in module.build_entities(coordinator)]
    keys = [entity.unique_id for entity in entities]
    assert not any(word in key for key in keys for word in ("filter_reset", "led_test", "dealer"))
    assert not any("egg_timer" in entity.unique_id for entity in number.build_entities(coordinator))
