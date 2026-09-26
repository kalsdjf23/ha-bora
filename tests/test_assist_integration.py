"""Exercise Assist through real HA entity services with a simulated BLE peer."""

from unittest.mock import patch

import pytest
from homeassistant import setup
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_assist import START_PATH, AssistConnection, program_status

from custom_components.bora.ble import zone
from custom_components.bora.ble.wire import Message
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"
UID = "back_right"
OPTION = "Fry pancakes (180 °C)"
ENABLED = {CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: True}


@pytest.fixture(autouse=True)
def custom_components(enable_custom_integrations):
    pass


@pytest.fixture
def entry_options(request):
    return getattr(request, "param", ENABLED)


@pytest.fixture
async def loaded(hass, entry_options):
    connection = AssistConnection()
    original = setup.async_process_deps_reqs

    async def dependencies(hass, config, integration):
        # Keep the real coordinator, platforms and service dispatch. Only the
        # Bluetooth dependency and its physical connection are substituted.
        if integration.domain == DOMAIN:
            return
        return await original(hass, config, integration)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="BORA X PURE",
        data={"address": ADDRESS},
        options=entry_options,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.setup.async_process_deps_reqs", side_effect=dependencies),
        patch("custom_components.bora.coordinator.create_connection", return_value=connection),
        patch(
            "homeassistant.components.bluetooth.async_register_callback", return_value=lambda: None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, connection
        if entry.state == ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


def entity_id(hass, domain, key):
    result = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ADDRESS}_{key}")
    assert result is not None
    return result


async def select_program(hass, option=OPTION):
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", f"{UID}_assist"), "option": option},
        blocking=True,
    )
    await hass.async_block_till_done()


async def press_start(hass):
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", f"{UID}_start_assist")},
        blocking=True,
    )


@pytest.mark.parametrize(
    "entry_options",
    [{}, {CONF_ENABLE_CONTROLS: True}, {CONF_ENABLE_COOKING: True}],
    indirect=True,
    ids=["default-off", "general-only", "cooking-only"],
)
async def test_services_cannot_operate_without_both_options(hass, loaded):
    entry, connection = loaded
    assert entry.state == ConfigEntryState.LOADED
    for uid in entry.runtime_data.device.zone_uids:
        for domain, key in (("select", f"{uid}_assist"), ("button", f"{uid}_start_assist")):
            assert hass.states.get(entity_id(hass, domain, key)).state == STATE_UNAVAILABLE
    before = list(connection.requests)
    # HA filters unavailable entities before calling their service methods.
    await select_program(hass)
    await press_start(hass)
    assert entry.runtime_data.assist_selections == {}
    assert connection.requests == before


async def test_select_service_is_local_and_button_starts_exactly_one_selected_zone(hass, loaded):
    entry, connection = loaded
    selection = entity_id(hass, "select", f"{UID}_assist")
    button = entity_id(hass, "button", f"{UID}_start_assist")
    assert hass.states.get(selection).state == STATE_UNKNOWN
    assert hass.states.get(button).state == STATE_UNAVAILABLE
    assert OPTION in hass.states.get(selection).attributes["options"]

    before = list(connection.requests)
    await select_program(hass)
    assert connection.requests == before
    assert hass.states.get(selection).state == OPTION
    assert hass.states.get(button).state == STATE_UNKNOWN

    await press_start(hass)
    await hass.async_block_till_done()
    writes = [body for path, body in connection.requests if path == START_PATH]
    assert len(writes) == 1
    assert Message(writes[0]).text(2) == UID
    assert Message(Message(writes[0]).bytes(1)).uint(1) == 63120
    assert hass.states.get(entity_id(hass, "sensor", f"{UID}_mode")).state == "csf"
    program = hass.states.get(entity_id(hass, "sensor", f"{UID}_csf"))
    assert program.state == "frying"
    assert program.attributes["phase"] == "confirmation_required"
    assert hass.states.get(button).state == STATE_UNAVAILABLE
    for uid in entry.runtime_data.device.zone_uids:
        if uid != UID:
            assert hass.states.get(entity_id(hass, "sensor", f"{uid}_mode")).state == "power_level"
    assert not any(
        "Confirmation" in path or "SetBridged" in path for path, _ in connection.requests
    )


async def test_unconfirmed_service_start_disables_button_and_cannot_be_repeated(hass, loaded):
    entry, connection = loaded
    connection.apply_start = False
    await select_program(hass)
    with pytest.raises(HomeAssistantError, match="does not yet show"):
        await press_start(hass)
    await hass.async_block_till_done()

    button = entity_id(hass, "button", f"{UID}_start_assist")
    assert hass.states.get(button).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, "sensor", f"{UID}_mode")).state == "power_level"
    assert entry.runtime_data.last_update_success
    assert sum(path == START_PATH for path, _ in connection.requests) == 1
    before = list(connection.requests)
    await press_start(hass)
    # A different local selection must not bypass the uncertain-start guard.
    await select_program(hass, "Cook egg dishes (135 °C)")
    await press_start(hass)
    assert hass.states.get(button).state == STATE_UNAVAILABLE
    assert connection.requests == before


async def test_received_program_states_follow_phases_and_ignore_local_selection(hass, loaded):
    _entry, connection = loaded
    phase = entity_id(hass, "sensor", f"{UID}_csf_phase")
    program = entity_id(hass, "sensor", f"{UID}_csf")
    target = entity_id(hass, "sensor", f"{UID}_assist_target")
    confirmation = entity_id(hass, "binary_sensor", f"{UID}_assist_confirmation_required")
    idle_status = connection.responses[zone.get_status(UID)]

    await select_program(hass)
    assert hass.states.get(program).state == STATE_UNKNOWN
    assert hass.states.get(program).attributes["catalogue_program"] is None
    assert hass.states.get(target).state == STATE_UNKNOWN
    assert hass.states.get(phase).state == "inactive"
    assert hass.states.get(confirmation).state == STATE_OFF

    await press_start(hass)
    await hass.async_block_till_done()
    writes = [body for path, body in connection.requests if path == START_PATH]
    assert len(writes) == 1
    parameters = Message(writes[0]).bytes(1)
    assert hass.states.get(program).state == "frying"
    assert hass.states.get(program).attributes["catalogue_program"] == "Fry pancakes"
    assert hass.states.get(phase).state == "confirmation_required"
    assert hass.states.get(confirmation).state == STATE_ON
    assert float(hass.states.get(target).state) == 180
    assert hass.states.get(target).attributes["unit_of_measurement"] == "°C"

    for raw_phase, name in ((99, "unknown_99"), (0, "unspecified")):
        connection.streams[zone.STREAM_PATH](program_status(UID, parameters, raw_phase))
        await hass.async_block_till_done()
        assert hass.states.get(phase).state == name
        assert hass.states.get(confirmation).state == STATE_UNKNOWN

    # A received target can differ from the catalogue default; display the
    # actual setting while the program proceeds, without sending another write.
    received = zone.decode_csf_parameter(parameters)
    received.pop("present_fields")
    received.pop("csf_time_to_set_obsolete")
    received["csf_type_target_value"] = 190
    connection.streams[zone.STREAM_PATH](
        program_status(UID, zone.encode_csf_parameter(received), phase=3)
    )
    await hass.async_block_till_done()
    assert hass.states.get(phase).state == "active"
    assert hass.states.get(confirmation).state == STATE_OFF
    assert float(hass.states.get(target).state) == 190

    before = list(connection.requests)
    await select_program(hass, "Cook egg dishes (135 °C)")
    assert connection.requests == before
    assert hass.states.get(program).attributes["catalogue_program"] == "Fry pancakes"
    assert hass.states.get(phase).state == "active"
    assert hass.states.get(confirmation).state == STATE_OFF
    assert float(hass.states.get(target).state) == 190

    connection.streams[zone.STREAM_PATH](idle_status)
    await hass.async_block_till_done()
    assert hass.states.get(phase).state == "inactive"
    assert hass.states.get(confirmation).state == STATE_OFF
    assert hass.states.get(program).state == STATE_UNKNOWN
    assert hass.states.get(program).attributes["catalogue_program"] is None
    assert hass.states.get(target).state == STATE_UNKNOWN
    assert connection.requests == before


@pytest.mark.parametrize("applied", [False, True], ids=["unconfirmed", "confirmed"])
async def test_unload_and_reload_do_not_restore_selection_or_replay_start(hass, loaded, applied):
    entry, connection = loaded
    connection.apply_start = applied
    await select_program(hass)
    if applied:
        await press_start(hass)
    else:
        with pytest.raises(HomeAssistantError, match="does not yet show"):
            await press_start(hass)
    await hass.async_block_till_done()
    before = len(connection.requests)
    old_coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not connection.connected
    assert not connection.streams
    assert len(connection.requests) == before

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data is not old_coordinator
    assert entry.runtime_data.assist_selections == {}
    assert hass.states.get(entity_id(hass, "select", f"{UID}_assist")).state == STATE_UNKNOWN
    start_state = hass.states.get(entity_id(hass, "button", f"{UID}_start_assist"))
    assert start_state.state == STATE_UNAVAILABLE
    assert sum(path == START_PATH for path, _ in connection.requests) == 1
    assert all("/Get" in path for path, _ in connection.requests[before:])
