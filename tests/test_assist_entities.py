"""Assist selection and explicit start with a fake coordinator, no appliance I/O."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from test_entities import recorded_bodies

from custom_components.bora import button, select
from custom_components.bora.ble import cooktop, identify, presets, zone

UID = "front_left"
OTHER_UID = "back_right"


@pytest.fixture
def coordinator():
    bodies = recorded_bodies()
    entry = SimpleNamespace(entry_id="fixture", unique_id="AA:BB:CC:DD:EE:FF", title="BORA fixture")
    result = SimpleNamespace(
        entry=entry,
        device=SimpleNamespace(
            information={"product": 2, "product_name": "x_pure"},
            descriptor=identify.decode_descriptor(bodies["device-descriptor-1"]),
            assist_start_blocked=Mock(return_value=False),
        ),
        data={
            "cooktop": cooktop.decode_status(bodies["cooktop-status-1"]),
            "zones": {
                status["uid"]: status
                for name, body in bodies.items()
                if name.startswith("zone-status-")
                for status in [zone.decode_status(body)]
            },
        },
        controls_enabled=True,
        cooking_enabled=True,
        last_update_success=True,
        assist_selections={},
        async_update_listeners=Mock(),
        async_start_assist=AsyncMock(),
        async_execute=AsyncMock(),
    )
    result.assist_presets = lambda uid: presets.get_presets(
        result.device.information, result.device.descriptor, uid
    )

    def select_assist(uid, preset_id):
        result.assist_selections[uid] = preset_id
        result.async_update_listeners()

    result.select_assist = Mock(side_effect=select_assist)
    entry.runtime_data = result
    return result


def choice(coordinator, uid=UID):
    return next(
        entity
        for entity in select.build_entities(coordinator)
        if entity.unique_id == f"{coordinator.entry.unique_id}_{uid}_assist"
    )


def start_button(coordinator, uid=UID):
    return next(
        entity
        for entity in button.build_entities(coordinator)
        if entity.unique_id == f"{coordinator.entry.unique_id}_{uid}_start_assist"
    )


async def test_selection_has_no_default_and_never_starts_a_program(coordinator):
    selected, start = choice(coordinator), start_button(coordinator)
    assert selected.available
    assert selected.current_option is None
    assert not start.available
    assert selected.options == [
        "Cook egg dishes (135 °C)",
        "Fry potato dishes (205 °C)",
        "Fry pancakes (180 °C)",
        "Fry breaded foods (170 °C)",
    ]
    await selected.async_select_option("Fry potato dishes (205 °C)")
    assert selected.current_option == "Fry potato dishes (205 °C)"
    assert coordinator.assist_selections == {UID: 62954}
    coordinator.select_assist.assert_called_once_with(UID, 62954)
    coordinator.async_update_listeners.assert_called_once_with()
    coordinator.async_start_assist.assert_not_awaited()
    coordinator.async_execute.assert_not_awaited()
    assert start.available


async def test_only_explicit_button_press_dispatches_the_selected_zone(coordinator):
    selected, start = choice(coordinator, OTHER_UID), start_button(coordinator, OTHER_UID)
    await selected.async_select_option("Fry pancakes (180 °C)")
    assert not start_button(coordinator, UID).available
    await start.async_press()
    coordinator.async_start_assist.assert_awaited_once_with(OTHER_UID)
    coordinator.async_execute.assert_not_awaited()


async def test_pending_or_uncertain_start_disables_button(coordinator):
    coordinator.assist_selections[UID] = 62176
    coordinator.device.assist_start_blocked.return_value = True
    start = start_button(coordinator)
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize(("controls", "cooking"), [(False, False), (False, True), (True, False)])
async def test_both_control_options_guard_selection_and_start(coordinator, controls, cooking):
    coordinator.controls_enabled = controls
    coordinator.cooking_enabled = cooking
    coordinator.assist_selections[UID] = 62176
    selected, start = choice(coordinator), start_button(coordinator)
    assert not selected.available
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await selected.async_select_option("Cook egg dishes (135 °C)")
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.select_assist.assert_not_called()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize("selection", [None, 99999, True])
async def test_start_requires_an_explicit_current_supported_selection(coordinator, selection):
    if selection is not None:
        coordinator.assist_selections[UID] = selection
    start = start_button(coordinator)
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.async_start_assist.assert_not_awaited()


async def test_invalid_label_does_not_change_local_selection(coordinator):
    selected = choice(coordinator)
    for label in ("62176", "Cook egg dishes", "Fry pancakes (205 °C)"):
        with pytest.raises(HomeAssistantError, match="not advertised or supported"):
            await selected.async_select_option(label)
    assert coordinator.assist_selections == {}
    coordinator.select_assist.assert_not_called()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize(
    "changed",
    [
        {"mode": "csf"},
        {"mode": "unknown"},
        {"power_level": 3},
        {"power_level": None},
        {"settings_present": False},
        {"settings_present": None},
        {"bridged": True},
        {"bridged": None},
        {"bridged_to_uid": "back_left"},
    ],
)
async def test_start_requires_known_idle_unbridged_zone(coordinator, changed):
    coordinator.assist_selections[UID] = 62176
    start = start_button(coordinator)
    assert start.available
    coordinator.data["zones"][UID].update(changed)
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize("missing", ["pure", "zone", "connection"])
async def test_start_rechecks_live_availability(coordinator, missing):
    coordinator.assist_selections[UID] = 62176
    start = start_button(coordinator)
    if missing == "pure":
        coordinator.data["cooktop"]["cooktop_settings"]["pure"] = None
    elif missing == "zone":
        coordinator.data["zones"][UID] = None
    else:
        coordinator.last_update_success = False
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.async_start_assist.assert_not_awaited()


async def test_capability_loss_invalidates_selection_without_autostart(coordinator):
    selected, start = choice(coordinator), start_button(coordinator)
    await selected.async_select_option("Cook egg dishes (135 °C)")
    zone_descriptor = coordinator.device.descriptor["zone_descriptor"]["zone_mode_descriptor"]
    next(item for item in zone_descriptor if item["u_id"] == UID)["supported_csf"] = []
    assert selected.options == []
    assert selected.current_option is None
    assert not selected.available
    assert not start.available
    with pytest.raises(HomeAssistantError):
        await start.async_press()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize("product", [None, 1, 6])
def test_unsupported_products_do_not_get_assist_entities(coordinator, product):
    coordinator.device.information["product"] = product
    assert not any(
        isinstance(entity, select.BoraAssistSelect) for entity in select.build_entities(coordinator)
    )
    assert not any(
        isinstance(entity, button.BoraStartAssistButton)
        for entity in button.build_entities(coordinator)
    )


def test_only_supported_descriptor_zones_get_assist_entities(coordinator):
    zones = coordinator.device.descriptor["zone_descriptor"]["zone_mode_descriptor"]
    next(item for item in zones if item["u_id"] == OTHER_UID)["supported_csf"] = []
    selects = [
        item
        for item in select.build_entities(coordinator)
        if isinstance(item, select.BoraAssistSelect)
    ]
    starts = [
        item
        for item in button.build_entities(coordinator)
        if isinstance(item, button.BoraStartAssistButton)
    ]
    assert len(selects) == len(starts) == 3
    assert not any(OTHER_UID in item.unique_id for item in (*selects, *starts))


def test_entity_recreation_does_not_restore_or_default_a_choice(coordinator):
    coordinator.assist_selections = {}
    for _ in range(2):
        assert choice(coordinator).current_option is None
        assert not start_button(coordinator).available
    assert coordinator.assist_selections == {}
    coordinator.select_assist.assert_not_called()
    coordinator.async_start_assist.assert_not_awaited()


@pytest.mark.parametrize("platform", [select, button])
async def test_platform_setup_adds_assists_without_dispatching(coordinator, platform):
    entities = []
    await platform.async_setup_entry(None, coordinator.entry, entities.extend)
    assert len({item.unique_id for item in entities}) == len(entities)
    assert len([
        item for item in entities
        if isinstance(item, select.BoraAssistSelect | button.BoraStartAssistButton)
    ]) == 4
    coordinator.select_assist.assert_not_called()
    coordinator.async_start_assist.assert_not_awaited()
