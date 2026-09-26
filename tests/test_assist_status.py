"""Reported Assist state remains independent of drafts, writes and temperature measurements."""

from types import SimpleNamespace

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature
from test_assist import UID, AssistConnection, program_status
from test_entities import entity_for

from custom_components.bora import binary_sensor, sensor
from custom_components.bora.ble import presets, zone
from custom_components.bora.ble.client import BoraDevice
from custom_components.bora.ble.wire import Message


@pytest.fixture
async def coordinator():
    connection = AssistConnection()
    device = BoraDevice(connection)
    await device.initialize()
    result = SimpleNamespace(
        entry=SimpleNamespace(entry_id="fixture", title="BORA fixture"),
        device=device,
        data=device.snapshot,
        last_update_success=True,
        controls_enabled=False,
        cooking_enabled=False,
        assist_selections={UID: 63121},
    )
    yield result
    assert all("/Get" in path for path, _ in connection.requests)
    await device.shutdown()


def observed(coordinator, preset_id=62176, phase=2, uid=UID):
    command = presets.prepare_preset(
        coordinator.device.information, coordinator.device.descriptor, uid, preset_id, 0
    )
    status = zone.decode_status(program_status(uid, Message(command[1]).bytes(1), phase))
    coordinator.data["zones"][uid] = status
    return status


@pytest.mark.parametrize(
    "phase,label,required",
    [
        (0, "unspecified", None),
        (1, "preheat", False),
        (2, "confirmation_required", True),
        (3, "active", False),
        (4, "expired", False),
        (99, "unknown_99", None),
    ],
)
async def test_phases_and_confirmation_follow_received_state(coordinator, phase, label, required):
    observed(coordinator, phase=phase)
    state = entity_for(sensor, coordinator, f"{UID}_csf_phase")
    confirmation = entity_for(binary_sensor, coordinator, f"{UID}_assist_confirmation_required")
    assert state.available
    assert state.native_value == label
    assert confirmation.available
    assert confirmation.is_on is required
    assert not coordinator.controls_enabled


@pytest.mark.parametrize("mode", ["power_level", "heat_retention", "heat_up"])
async def test_leaving_program_clears_phase_confirmation_and_target(coordinator, mode):
    status = observed(coordinator)
    status["mode"] = mode
    # Even a stale CSF object in a caller's snapshot must not be interpreted.
    assert entity_for(sensor, coordinator, f"{UID}_csf_phase").native_value == "inactive"
    assert (
        entity_for(binary_sensor, coordinator, f"{UID}_assist_confirmation_required").is_on is False
    )
    assert entity_for(sensor, coordinator, f"{UID}_assist_target").native_value is None
    assert (
        entity_for(sensor, coordinator, f"{UID}_csf").extra_state_attributes["catalogue_program"]
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "unknown"},
        {"mode": None},
        {"settings_present": False},
        {"csf": None},
        {"csf": {"parameters": None}},
    ],
)
async def test_missing_state_never_claims_confirmation_completed(coordinator, changes):
    observed(coordinator).update(changes)
    assert entity_for(sensor, coordinator, f"{UID}_csf_phase").native_value is None
    assert (
        entity_for(binary_sensor, coordinator, f"{UID}_assist_confirmation_required").is_on is None
    )
    assert entity_for(sensor, coordinator, f"{UID}_assist_target").native_value is None


@pytest.mark.parametrize("preset", presets.CATALOG)
async def test_received_catalogue_identity_and_target_are_not_local_selection(coordinator, preset):
    observed(coordinator, preset.preset_id)
    program = entity_for(sensor, coordinator, f"{UID}_csf")
    target = entity_for(sensor, coordinator, f"{UID}_assist_target")
    assert program.extra_state_attributes["catalogue_program"] == preset.name
    assert target.native_value == preset.target_celsius
    assert target.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert target.device_class == SensorDeviceClass.TEMPERATURE
    assert target.state_class is None  # A setting, not a temperature measurement.


async def test_reported_adjustment_is_not_replaced_with_recipe_default(coordinator):
    status = observed(coordinator)
    status["csf"]["parameters"]["csf_type_target_value"] = 137
    assert entity_for(sensor, coordinator, f"{UID}_assist_target").native_value == 137


@pytest.mark.parametrize(
    "changes",
    [
        {"csf_id": 99999},
        {"csf_type": 3},
        {"csf_type": 99},
        {"csf_type_target_value": 0},
        {"csf_type_target_value": 221},
        {"csf_type_target_value": None},
        {"csf_type_target_value": True},
    ],
)
async def test_unknown_or_out_of_range_target_is_not_labelled_celsius(coordinator, changes):
    parameters = observed(coordinator)["csf"]["parameters"]
    parameters.update(changes)
    assert entity_for(sensor, coordinator, f"{UID}_assist_target").native_value is None
    assert (
        entity_for(sensor, coordinator, f"{UID}_csf").extra_state_attributes["parameters_raw"]
        == parameters
    )


async def test_each_zone_uses_its_own_received_program(coordinator):
    for uid, preset in zip(coordinator.data["zones"], presets.CATALOG, strict=True):
        observed(coordinator, preset.preset_id, uid=uid)
    for uid, preset in zip(coordinator.data["zones"], presets.CATALOG, strict=True):
        assert (
            entity_for(sensor, coordinator, f"{uid}_assist_target").native_value
            == preset.target_celsius
        )


async def test_loss_of_connection_makes_program_sensors_unavailable(coordinator):
    observed(coordinator)
    coordinator.last_update_success = False
    for key in (f"{UID}_csf", f"{UID}_csf_phase", f"{UID}_assist_target"):
        assert not entity_for(sensor, coordinator, key).available
    assert not entity_for(
        binary_sensor, coordinator, f"{UID}_assist_confirmation_required"
    ).available


async def test_other_products_do_not_inherit_catalogue_temperature_units(coordinator):
    observed(coordinator)
    coordinator.device.information["product"] = 99
    assert not any(
        entity.unique_id.endswith("_assist_target") for entity in sensor.build_entities(coordinator)
    )
    assert (
        entity_for(sensor, coordinator, f"{UID}_csf").extra_state_attributes["catalogue_program"]
        is None
    )
