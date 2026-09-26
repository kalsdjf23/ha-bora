"""Timestamp successful Wi-Fi reads without shifting them to collection end."""

import asyncio
from datetime import UTC, datetime

import pytest
from test_diagnostics import Connection, successful_responses

from custom_components.bora.ble import diagnostic_client, identify
from custom_components.bora.ble.transport import RequestTimeout, RpcError
from custom_components.bora.ble.wire import Stream


async def test_wifi_timestamp_records_receipt_before_later_query_delay(freezer):
    freezer.move_to("2026-09-26T09:00:00+00:00")
    wifi_requested = asyncio.Event()
    release_wifi = asyncio.Event()
    later_requested = asyncio.Event()
    release_later = asyncio.Event()

    class DelayedConnection(Connection):
        async def rpc(self, path, body=b""):
            if path == identify.get_wifi_status()[0]:
                wifi_requested.set()
                await release_wifi.wait()
            elif path == identify.get_heartbeat_status()[0]:
                later_requested.set()
                await release_later.wait()
            return await super().rpc(path, body)

    connection = DelayedConnection(successful_responses())
    collecting = asyncio.create_task(diagnostic_client.async_collect(connection))
    await wifi_requested.wait()
    received_at = datetime(2026, 9, 26, 10, tzinfo=UTC)
    freezer.move_to(received_at)
    release_wifi.set()
    await later_requested.wait()
    freezer.move_to("2026-09-26T11:00:00+00:00")
    release_later.set()
    result = await collecting

    assert datetime.fromisoformat(result["wifi_status"]["read_at"]) == received_at
    assert result["wifi_status"]["read_at"].endswith("+00:00")
    assert result["wifi_status"]["data"]["connection_status"] == 4
    assert all("read_at" not in value for name, value in result.items() if name != "wifi_status")
    assert len(connection.calls) == len(set(connection.calls)) == 6


@pytest.mark.parametrize(
    "reply",
    [
        RpcError(
            12, request_id=1, path=identify.get_wifi_status()[0], stream=Stream.NONE,
        ),
        RequestTimeout("No reply"),
        b"\x0a\x80",
    ],
    ids=["unsupported", "timeout", "invalid_response"],
)
async def test_failed_wifi_read_has_no_timestamp(reply):
    responses = successful_responses()
    responses[identify.get_wifi_status()[0]] = reply
    connection = Connection(responses)
    result = await diagnostic_client.async_collect(connection)

    assert result["wifi_status"]["status"] in {"unsupported", "error"}
    assert "read_at" not in result["wifi_status"]
    assert "data" not in result["wifi_status"]
    assert all("read_at" not in value for value in result.values())
    assert result["saved_csf"]["status"] == "ok"
    assert len(connection.calls) == 6


async def test_absent_wifi_wrapper_is_timestamped_without_fabricated_status(freezer):
    freezer.move_to("2026-09-26T12:00:00+00:00")
    responses = successful_responses()
    responses[identify.get_wifi_status()[0]] = b""

    result = await diagnostic_client.async_collect(Connection(responses))

    assert result["wifi_status"] == {
        "status": "ok", "data": None, "read_at": "2026-09-26T12:00:00+00:00",
    }
