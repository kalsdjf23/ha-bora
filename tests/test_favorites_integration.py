"""Explicit favorite reads through real HA services with no hardware access."""

import asyncio
from datetime import UTC, datetime

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from test_integration import ADDRESS
from test_integration import custom_components as custom_components
from test_integration import loaded as loaded

from custom_components.bora.ble import identify
from custom_components.bora.ble.transport import RequestTimeout, RpcError
from custom_components.bora.ble.wire import blob, uint
from custom_components.bora.const import DOMAIN

SAVED = identify.get_saved_csf()
SLOTS = (3, 4, 5)


def entity_id(hass, domain, key):
    result = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ADDRESS}_{key}")
    assert result is not None
    return result


def slot_state(hass, slot):
    return hass.states.get(entity_id(hass, "sensor", f"saved_assist_{slot}"))


def saved_record(slot, recipe=62176, csf_type=2):
    # Timer/target/flags are intentionally raw values, not catalogue defaults.
    return blob(
        1,
        uint(1, recipe) + uint(3, slot) + uint(4, csf_type)
        + uint(5, 137) + uint(10, 128) + uint(11, 12345),
    )


async def press(hass, key="refresh_saved_assists"):
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", key)}, blocking=True
    )


async def test_explicit_service_populates_then_replaces_the_complete_saved_bank(hass, loaded):
    entry, connection = loaded
    assert not entry.runtime_data.controls_enabled
    assert not entry.runtime_data.cooking_enabled
    assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)
    connection.responses[SAVED] = (
        saved_record(3) + saved_record(4, 99999, 42)
        + saved_record(5, 62954) + saved_record(5, 63120)
    )
    before = len(connection.requests)
    earliest = datetime.now(UTC)
    await press(hass)
    await hass.async_block_till_done()
    latest = datetime.now(UTC)
    assert connection.requests[before:] == [SAVED]
    assert slot_state(hass, 3).state == "Cook egg dishes"
    assert slot_state(hass, 3).attributes["recognition"] == "known"
    assert slot_state(hass, 4).state == "unknown_99999"
    assert slot_state(hass, 4).attributes["recognition"] == "unknown"
    assert slot_state(hass, 5).state == "ambiguous"
    assert slot_state(hass, 5).attributes["recognition"] == "ambiguous"
    assert slot_state(hass, 5).attributes["parameters_raw"] is None
    assert len(slot_state(hass, 5).attributes["ambiguous_parameters_raw"]) == 2
    raw = slot_state(hass, 3).attributes["parameters_raw"]
    assert raw["csf_type_target_value"] == 137
    assert raw["csf_timer_duration"] == 12345
    assert raw["csf_settings"] == 128
    timestamps = {slot_state(hass, slot).attributes["last_read"] for slot in SLOTS}
    assert len(timestamps) == 1
    assert earliest <= datetime.fromisoformat(timestamps.pop()) <= latest
    assert all("unit_of_measurement" not in slot_state(hass, slot).attributes for slot in SLOTS)

    connection.responses[SAVED] = b""
    await press(hass)
    await hass.async_block_till_done()
    assert connection.requests[before:] == [SAVED, SAVED]
    for slot in SLOTS:
        current = slot_state(hass, slot)
        assert current.state == "empty"
        assert current.attributes["recognition"] == "empty"
        assert current.attributes["parameters_raw"] is None
        assert current.attributes["ambiguous_parameters_raw"] == []
        assert current.attributes["slot"] == slot
        assert datetime.fromisoformat(current.attributes["last_read"]) >= latest
    assert entry.runtime_data.last_update_success


async def test_setup_poll_and_reload_never_automatically_read_favorites(hass, loaded):
    entry, connection = loaded
    connection.responses[SAVED] = saved_record(3)
    assert SAVED not in connection.requests
    await entry.runtime_data.async_refresh()
    assert SAVED not in connection.requests
    await press(hass)
    await hass.async_block_till_done()
    first_read = slot_state(hass, 3).attributes["last_read"]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert connection.requests.count(SAVED) == 1
    assert slot_state(hass, 3).attributes["last_read"] == first_read

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert connection.requests.count(SAVED) == 1
    assert entry.runtime_data.device.favorites_snapshot is None
    assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)
    assert hass.states.get(entity_id(hass, "button", "refresh_saved_assists")).state != (
        STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("failure", ["unsupported", "timeout", "malformed"])
async def test_failed_refresh_clears_old_favorites_without_disabling_status(hass, loaded, failure):
    entry, connection = loaded
    connection.responses[SAVED] = saved_record(3)
    await press(hass)
    await hass.async_block_till_done()
    assert slot_state(hass, 3).state == "Cook egg dishes"
    original = connection.rpc

    async def failing_rpc(path, body=b"", *, received=None, failed=None):
        if (path, body) == SAVED:
            connection.requests.append((path, body))
            if failure == "unsupported":
                error = RpcError(12)
                if failed:
                    failed(error)
                raise error
            if failure == "timeout":
                raise RequestTimeout("Simulated optional request timeout")
            return b"\x80"
        return await original(path, body, received=received, failed=failed)

    connection.rpc = failing_rpc
    with pytest.raises(HomeAssistantError, match="could not be read"):
        await press(hass)
    await hass.async_block_till_done()
    assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)
    assert entry.runtime_data.device.favorites_snapshot is None
    assert entry.runtime_data.last_update_success
    assert connection.connected
    assert hass.states.get(entity_id(hass, "sensor", "front_left_mode")).state == "power_level"
    assert connection.requests.count(SAVED) == 2


async def test_cancelled_service_read_clears_cache_and_allows_a_later_explicit_read(hass, loaded):
    entry, connection = loaded
    connection.responses[SAVED] = saved_record(3)
    await press(hass)
    entered = asyncio.Event()
    original = connection.rpc

    async def waiting_rpc(path, body=b"", *, received=None, failed=None):
        if (path, body) == SAVED:
            connection.requests.append((path, body))
            entered.set()
            await asyncio.Future()
        return await original(path, body, received=received, failed=failed)

    connection.rpc = waiting_rpc
    task = asyncio.create_task(press(hass))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert entry.runtime_data.device.favorites_snapshot is None
        assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success
    assert connection.connected
    assert connection.requests.count(SAVED) == 2
    connection.rpc = original
    connection.responses[SAVED] = b""
    await press(hass)
    await hass.async_block_till_done()
    assert connection.requests.count(SAVED) == 3
    assert all(slot_state(hass, slot).state == "empty" for slot in SLOTS)


async def test_disconnect_invalidates_slots_and_reconnect_does_not_refetch_them(hass, loaded):
    entry, connection = loaded
    connection.responses[SAVED] = saved_record(3)
    await press(hass)
    await connection.disconnect()
    entry.runtime_data._on_disconnect()  # Simulate the adapter's disconnect callback.
    await hass.async_block_till_done()
    assert not entry.runtime_data.last_update_success
    assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success
    assert connection.requests.count(SAVED) == 1
    assert all(slot_state(hass, slot).state == STATE_UNAVAILABLE for slot in SLOTS)


async def test_diagnostics_button_reuses_its_one_saved_response_for_slot_states(hass, loaded):
    entry, connection = loaded
    registry = er.async_get(hass)
    diagnostics = entity_id(hass, "button", "refresh_diagnostics")
    registry.async_update_entity(diagnostics, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert SAVED not in connection.requests
    connection.responses[SAVED] = saved_record(4, 63121)
    before = len(connection.requests)
    await press(hass, "refresh_diagnostics")
    await hass.async_block_till_done()
    queries = connection.requests[before:]
    assert len(queries) == 6
    assert queries.count(SAVED) == 1
    assert all("/Get" in path or "/List" in path for path, _ in queries)
    assert slot_state(hass, 4).state == "Fry breaded foods"
    assert slot_state(hass, 3).state == slot_state(hass, 5).state == "empty"
    assert entry.runtime_data.last_update_success
    assert not entry.runtime_data.controls_enabled
    assert not entry.runtime_data.cooking_enabled
