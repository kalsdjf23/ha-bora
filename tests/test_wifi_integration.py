"""Optional Wi-Fi snapshots through real HA services and a simulated BLE peer."""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.helpers import entity_registry as er
from test_diagnostics import successful_responses
from test_integration import ADDRESS
from test_integration import custom_components as custom_components
from test_integration import loaded as loaded

from custom_components.bora.ble import identify
from custom_components.bora.ble.transport import RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream, blob, string, uint
from custom_components.bora.const import DOMAIN

WIFI = identify.get_wifi_status()
OPTIONAL = (
    WIFI, identify.get_heartbeat_status(), identify.get_heartbeat_period(),
    identify.list_sys_events(20), identify.list_user_events(20), identify.get_saved_csf(),
)


def entity_id(hass, domain, key):
    result = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ADDRESS}_{key}")
    assert result is not None
    return result


def wifi_state(hass):
    return hass.states.get(entity_id(hass, "sensor", "wifi_status"))


def wifi_reply(code):
    return blob(
        1, uint(1, code) + string(2, "PRIVATE_NETWORK")
        + blob(3, bytes.fromhex("aabbccddeeff")) + uint(4, 0xC0000201)
        + string(5, "PRIVATE_TIME_ZONE"),
    )


async def press_diagnostics(hass):
    await hass.services.async_call(
        "button", "press",
        {"entity_id": entity_id(hass, "button", "refresh_diagnostics")},
        blocking=True,
    )


@pytest.fixture
async def wifi_enabled(hass, loaded):
    entry, connection = loaded
    registry = er.async_get(hass)
    for domain, key in (("sensor", "wifi_status"), ("button", "refresh_diagnostics")):
        registry.async_update_entity(entity_id(hass, domain, key), disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    responses = successful_responses()
    for command in OPTIONAL:
        connection.responses[command] = responses[command[0]]
    assert WIFI not in connection.requests
    return entry, connection


async def test_wifi_sensor_and_refresh_button_are_disabled_in_registry_by_default(hass, loaded):
    entry, connection = loaded
    registry = er.async_get(hass)
    for domain, key in (("sensor", "wifi_status"), ("button", "refresh_diagnostics")):
        identifier = entity_id(hass, domain, key)
        record = registry.async_get(identifier)
        assert record.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert record.entity_category is EntityCategory.DIAGNOSTIC
        assert hass.states.get(identifier) is None
    await entry.runtime_data.async_refresh()
    assert WIFI not in connection.requests


async def test_explicit_service_updates_distinct_wifi_states_with_controls_off(hass, wifi_enabled):
    entry, connection = wifi_enabled
    assert not entry.runtime_data.controls_enabled
    assert not entry.runtime_data.cooking_enabled
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    for code, label in (
        (4, "wifi_connected"), (8, "no_internet"), (9, "internet_access"),
        (99, "unknown_99"), (0, "unspecified"),
    ):
        connection.responses[WIFI] = wifi_reply(code)
        before = len(connection.requests)
        earliest = datetime.now(UTC)
        await press_diagnostics(hass)
        await hass.async_block_till_done()
        latest = datetime.now(UTC)
        assert connection.requests[before:] == list(OPTIONAL)
        state = wifi_state(hass)
        assert state.state == label
        assert state.attributes["connection_status"] == code
        assert earliest <= datetime.fromisoformat(state.attributes["last_read"]) <= latest
        assert set(state.attributes) == {"friendly_name", "connection_status", "last_read"}
        assert "Last reported Wi-Fi status" in state.attributes["friendly_name"]
        assert "PRIVATE_" not in json.dumps(state.attributes)
        assert "aa:bb:cc:dd:ee:ff" not in json.dumps(state.attributes)

    last_read = wifi_state(hass).attributes["last_read"]
    reads = connection.requests.count(WIFI)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert connection.requests.count(WIFI) == reads
    assert wifi_state(hass).attributes["last_read"] == last_read
    assert wifi_state(hass).state == "unspecified"


@pytest.mark.parametrize("failure", ["unsupported", "timeout", "malformed", "missing_status"])
async def test_failed_explicit_read_removes_wifi_state_without_disabling_status(
    hass, wifi_enabled, failure
):
    entry, connection = wifi_enabled
    connection.responses[WIFI] = wifi_reply(4)
    await press_diagnostics(hass)
    await hass.async_block_till_done()
    assert wifi_state(hass).state == "wifi_connected"
    connection.responses[WIFI] = {
        "unsupported": RpcError(12, request_id=1, path=WIFI[0], stream=Stream.NONE),
        "timeout": RequestTimeout("Simulated optional timeout"),
        "malformed": b"\x80",
        "missing_status": b"",
    }[failure]
    before = len(connection.requests)
    await press_diagnostics(hass)
    await hass.async_block_till_done()
    assert connection.requests[before:] == list(OPTIONAL)
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    assert "last_read" not in wifi_state(hass).attributes
    assert "connection_status" not in wifi_state(hass).attributes
    assert entry.runtime_data.last_update_success
    assert connection.connected


async def test_cancelled_refresh_clears_wifi_state_without_replaying_the_read(hass, wifi_enabled):
    entry, connection = wifi_enabled
    connection.responses[WIFI] = wifi_reply(4)
    await press_diagnostics(hass)
    await hass.async_block_till_done()
    assert wifi_state(hass).state == "wifi_connected"
    entered = asyncio.Event()
    original = connection.rpc

    async def waiting_rpc(path, body=b"", *, received=None, failed=None):
        if (path, body) == WIFI:
            connection.requests.append((path, body))
            entered.set()
            await asyncio.Future()
        return await original(path, body, received=received, failed=failed)

    connection.rpc = waiting_rpc
    before = len(connection.requests)
    task = asyncio.create_task(press_diagnostics(hass))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        connection.rpc = original
    await hass.async_block_till_done()
    assert connection.requests[before:] == [WIFI]
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    assert "last_read" not in wifi_state(hass).attributes
    assert entry.runtime_data.last_update_success
    assert connection.connected


async def test_disconnect_reconnect_and_reload_never_restore_or_refetch_wifi(hass, wifi_enabled):
    entry, connection = wifi_enabled
    connection.responses[WIFI] = wifi_reply(4)
    await press_diagnostics(hass)
    await hass.async_block_till_done()
    assert wifi_state(hass).state == "wifi_connected"
    await connection.disconnect()
    entry.runtime_data._on_disconnect()
    await hass.async_block_till_done()
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    assert connection.requests.count(WIFI) == 1

    await press_diagnostics(hass)
    await hass.async_block_till_done()
    assert wifi_state(hass).state == "wifi_connected"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert wifi_state(hass).state == STATE_UNAVAILABLE
    assert connection.requests.count(WIFI) == 2
