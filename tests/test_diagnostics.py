"""Optional diagnostics use bounded reads; exports contain no private IDs."""
import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from enum import IntEnum
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.bora import diagnostics
from custom_components.bora.ble import identify
from custom_components.bora.ble.diagnostic_client import async_collect
from custom_components.bora.ble.transport import RequestTimeout, RpcError
from custom_components.bora.ble.wire import blob, string, uint


class Connection:
    """Only RPC is available: no connect, write-control or subscribe surface."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def rpc(self, path, body=b""):
        self.calls.append((path, body))
        result = self.responses[path]
        if isinstance(result, BaseException):
            raise result
        return result


def successful_responses():
    return {
        identify.get_wifi_status()[0]: blob(1, uint(1, 4) + string(2, "Test WiFi")),
        identify.get_heartbeat_status()[0]: uint(1, 1) + uint(2, 123) + uint(3, 5000),
        identify.get_heartbeat_period()[0]: uint(1, 5000),
        identify.list_sys_events()[0]: blob(1, uint(1, 10) + uint(2, 33)),
        identify.list_user_events()[0]: blob(1, uint(1, 11) + uint(2, 5)),
        identify.get_saved_csf()[0]: blob(1, uint(1, 3) + uint(3, 2) + uint(4, 1)),
    }


async def test_collect_queries_each_optional_read_once_and_decodes_results():
    connection = Connection(successful_responses())
    result = await async_collect(connection)
    assert connection.calls == [
        identify.get_wifi_status(), identify.get_heartbeat_status(),
        identify.get_heartbeat_period(), identify.list_sys_events(20),
        identify.list_user_events(20), identify.get_saved_csf(),
    ]
    assert all(query["status"] == "ok" for query in result.values())
    assert result["wifi_status"]["data"]["connection_status"] == 4
    assert result["heartbeat_status"]["data"]["heartbeat_counter"] == 123
    assert result["heartbeat_period"]["data"] == {"heartbeat_period": 5000}
    assert result["sys_events"]["data"] == [{"timestamp": 10, "event_type": 33}]
    assert result["user_events"]["data"] == [{"timestamp": 11, "event_type": 5}]
    assert result["saved_csf"]["data"][0]["csf_index"] == 2
    assert all("/Heartbeat" not in path for path, _body in connection.calls)


async def test_unsupported_and_timeout_are_per_query_without_retry_or_fake_values():
    replies = successful_responses()
    replies[identify.get_wifi_status()[0]] = RpcError(12, b"private appliance details")
    replies[identify.get_heartbeat_status()[0]] = RequestTimeout("SSID Private WiFi")
    replies[identify.get_heartbeat_period()[0]] = RpcError(7, b"private bytes")
    replies[identify.list_sys_events()[0]] = TimeoutError("AA:BB:CC:DD:EE:FF")
    connection = Connection(replies)
    result = await async_collect(connection)
    assert result["wifi_status"] == {"status": "unsupported", "code": 12}
    assert result["heartbeat_status"] == {"status": "error", "error_type": "RequestTimeout"}
    assert result["heartbeat_period"] == {"status": "error", "code": 7}
    assert result["sys_events"] == {"status": "error", "error_type": "TimeoutError"}
    assert result["user_events"]["status"] == "ok"
    assert result["saved_csf"]["status"] == "ok"
    assert len(connection.calls) == len(set(connection.calls)) == 6
    output = json.dumps(result)
    assert "Private WiFi" not in output
    assert "AA:BB" not in output
    assert "private" not in output


async def test_decoder_errors_do_not_synthesize_defaults_and_other_reads_continue():
    replies = successful_responses()
    replies[identify.get_wifi_status()[0]] = b"\x0a\x80"
    connection = Connection(replies)
    result = await async_collect(connection)
    assert result["wifi_status"] == {"status": "error", "error_type": "ProtocolError"}
    assert result["heartbeat_status"]["status"] == "ok"
    assert len(connection.calls) == 6


async def test_cancelled_collection_stops_without_further_queries():
    connection = Connection({identify.get_wifi_status()[0]: asyncio.CancelledError()})
    with pytest.raises(asyncio.CancelledError):
        await async_collect(connection)
    assert connection.calls == [identify.get_wifi_status()]


class Flag(IntEnum):
    ACTIVE = 1


class PrivateOpaqueObject:
    def __repr__(self):
        return "opaque object contains PRIVATE_SERIAL"


async def test_download_redacts_nested_secrets_aliases_and_map_keys_without_reads():
    secret_serial = "PRIVATE_SERIAL"
    secret_ssid = "Household Network"
    secret_identifier = "MODULE-9876"
    private_mac = "aa:bb:cc:dd:ee:ff"
    private_uuid = "123e4567-e89b-42d3-a456-426614174000"  # Synthetic test identity.
    device = SimpleNamespace(
        information={
            "cm_identifier": secret_identifier,
            "cmSerialNumber": secret_serial,
            "fd": "FD000123", "eNr": "ENR000456",
            "cm_sw_version_no": "3.0.9", "product_name": "x_pure",
            "pure": {"product_meta_data": [
                {"serial_number": "COMPONENT_SECRET", "device_hw_version_no": "1.2"},
            ]},
        },
        descriptor={
            "zone_uids": {"left_down_zone_uid": "front_left"},
            "power_levels": [{"index": 9, "level_name": "P"}],
            "component_map": {secret_identifier: {"identifier": secret_identifier}},
        },
        snapshot={
            "zones": {"front_left": {"power_level": 0}},
            "adapter": private_mac,
            "message": f"Device {secret_identifier}, network {secret_ssid}",
            "opaque": PrivateOpaqueObject(),
            "raw": b"secret raw device data",
            "wrapped_raw": bytearray(b"more private data"),
            "view_raw": memoryview(b"private view"),
            "date": datetime(2026, 9, 25, tzinfo=UTC), "flag": Flag.ACTIVE,
            "numbers": (1, float("nan"), float("inf")),
            "uuid_alias": private_uuid,
            "network_alias": "connect 192.0.2.50 or [2001:db8::1]",
            "identifiers": {("bora", "SET_PRIVATE_ID")},
        },
        diagnostic_snapshot={
            "wifi_status": {"status": "ok", "data": {
                "ssid": secret_ssid, "mac_address": private_mac,
                "ip_v4_address": 0xC0000201,
            }},
            "nested": [{secret_serial: [secret_identifier, "FD000123", "ENR000456"]}],
            "bytes_key": {b"private-key": b"private value"},
            "errors": {"status": "error", "error_type": "RequestTimeout"},
        },
        connection=SimpleNamespace(rpc=AsyncMock()),
    )
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(device=device), data={"address": private_uuid},
        unique_id=private_uuid,
    )
    output = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    encoded = json.dumps(output, allow_nan=False)
    for private in (
        secret_serial, secret_ssid, secret_identifier, private_mac, private_uuid,
        "COMPONENT_SECRET", "FD000123", "ENR000456", "SET_PRIVATE_ID",
        "192.0.2.50", "2001:db8::1", "secret raw", "private-key", "PRIVATE_SERIAL",
    ):
        assert private.casefold() not in encoded.casefold()
    assert output["information"]["cm_identifier"] == diagnostics.REDACTED
    assert output["information"]["cm_sw_version_no"] == "3.0.9"
    assert output["information"]["product_name"] == "x_pure"
    assert output["descriptor"]["zone_uids"]["left_down_zone_uid"] == "front_left"
    assert output["snapshot"]["zones"]["front_left"]["power_level"] == 0
    assert output["descriptor"]["power_levels"] == [{"index": 9, "level_name": "P"}]
    assert output["snapshot"]["numbers"] == [1, None, None]
    assert output["snapshot"]["flag"] == 1
    assert output["diagnostic_snapshot"]["errors"]["error_type"] == "RequestTimeout"
    device.connection.rpc.assert_not_awaited()
    assert device.information["cm_identifier"] == secret_identifier
    assert secret_identifier in device.descriptor["component_map"]
    assert device.diagnostic_snapshot["wifi_status"]["data"]["ssid"] == secret_ssid


async def test_redacted_key_collisions_keep_both_values_and_source_is_unchanged():
    sources = {
        "information": {"serials": ["SECRET0001", "SECRET0002"]},
        "descriptor": {"lookup": {"SECRET0001": {"x": 1}, "SECRET0002": {"x": 2}}},
        "snapshot": {}, "diagnostic_snapshot": None,
    }
    original = deepcopy(sources)
    entry = SimpleNamespace(runtime_data=SimpleNamespace(device=SimpleNamespace(**sources)))
    output = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    assert len(output["descriptor"]["lookup"]) == 2
    assert list(output["descriptor"]["lookup"].values()) == [{"x": 1}, {"x": 2}]
    assert sources == original
    assert "SECRET" not in json.dumps(output)


async def test_default_numeric_identifiers_preserve_zero_status_but_redact_real_aliases():
    device = SimpleNamespace(
        information={"identifier": 0, "part_identifier": 123456},
        descriptor={"indices": [0, 1, 2]},
        snapshot={
            "power_level": 0, "timer": 0, "csf_settings": 0,
            "message": "level 0", "module_alias": 123456,
            "network_alias": 0xC0000201,
        },
        diagnostic_snapshot={
            "wifi_status": {"ip_v4_address": 0},
            "previous": {"ip_v4_address": 0xC0000201},
        },
    )
    entry = SimpleNamespace(runtime_data=SimpleNamespace(device=device))
    result = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    assert result["information"] == {
        "identifier": diagnostics.REDACTED, "part_identifier": diagnostics.REDACTED,
    }
    assert result["diagnostic_snapshot"]["wifi_status"]["ip_v4_address"] == diagnostics.REDACTED
    assert result["diagnostic_snapshot"]["previous"]["ip_v4_address"] == diagnostics.REDACTED
    assert result["descriptor"]["indices"] == [0, 1, 2]
    assert result["snapshot"] == {
        "power_level": 0, "timer": 0, "csf_settings": 0,
        "message": "level 0", "module_alias": diagnostics.REDACTED,
        "network_alias": diagnostics.REDACTED,
    }


async def test_string_zero_identifier_still_redacts_aliases():
    device = SimpleNamespace(information={"ssid": "0"}, snapshot={"alias": "network 0"})
    entry = SimpleNamespace(runtime_data=SimpleNamespace(device=device))
    result = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    assert result["information"]["ssid"] == diagnostics.REDACTED
    assert result["snapshot"]["alias"] == f"network {diagnostics.REDACTED}"


async def test_unloaded_entry_and_recursive_data_remain_json_safe():
    assert await diagnostics.async_get_config_entry_diagnostics(None, SimpleNamespace()) == {
        "information": None, "descriptor": None, "snapshot": None, "diagnostic_snapshot": None,
    }
    cycle = {}
    cycle["cycle"] = cycle
    entry = SimpleNamespace(runtime_data=SimpleNamespace(device=SimpleNamespace(snapshot=cycle)))
    result = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    assert result["snapshot"]["cycle"] == "<recursive reference>"
    json.dumps(result, allow_nan=False)


async def test_identifier_map_keys_and_short_ssid_are_redacted_in_aliases():
    device = SimpleNamespace(
        information={"identifiers": {"DEVICE_MAP_SECRET": 5}},
        diagnostic_snapshot={"ssid": "abc", "alias": "network abc", "copy": "DEVICE_MAP_SECRET"},
    )
    entry = SimpleNamespace(runtime_data=SimpleNamespace(device=device))
    result = await diagnostics.async_get_config_entry_diagnostics(None, entry)
    assert result["diagnostic_snapshot"]["alias"] == f"network {diagnostics.REDACTED}"
    assert result["diagnostic_snapshot"]["copy"] == diagnostics.REDACTED
    assert "DEVICE_MAP_SECRET" not in json.dumps(result)
