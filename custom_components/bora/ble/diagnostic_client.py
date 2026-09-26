"""Explicit, one-shot read-only diagnostics; never part of ordinary polling."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import identify
from .transport import RpcError

if TYPE_CHECKING:
    from .transport import BrpcConnection


async def async_collect(connection: BrpcConnection) -> dict[str, Any]:
    """Try each optional read once on the caller's existing connection.

    The caller decides when to invoke this and stores the returned snapshot.
    No reconnect, retry, heartbeat send, subscription or control is performed.
    Cancellation propagates. Failure of one optional query leaves the other
    query results usable; exception messages/raw RPC error bytes stay private.
    """
    queries = (
        ("wifi_status", identify.get_wifi_status(), identify.decode_wifi_status),
        ("heartbeat_status", identify.get_heartbeat_status(), identify.decode_heartbeat_status),
        ("heartbeat_period", identify.get_heartbeat_period(), identify.decode_heartbeat_period),
        ("sys_events", identify.list_sys_events(20), identify.decode_events),
        ("user_events", identify.list_user_events(20), identify.decode_events),
        ("saved_csf", identify.get_saved_csf(), identify.decode_saved_csf),
    )
    result: dict[str, Any] = {}
    for name, command, decoder in queries:
        try:
            body = await connection.rpc(*command)
            data = decoder(body)
        except RpcError as err:
            result[name] = {
                "status": "unsupported" if err.code == 12 else "error",
                "code": err.code,
            }
        except Exception as err:
            # A backend or decoder failure must not turn into a fabricated
            # zero-value snapshot, nor leak SSIDs/addresses in exception text.
            result[name] = {"status": "error", "error_type": type(err).__name__}
        else:
            result[name] = {"status": "ok", "data": data}
    return result
