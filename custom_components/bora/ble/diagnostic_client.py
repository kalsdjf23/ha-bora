"""Explicit, one-shot read-only diagnostics; never part of ordinary polling."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import identify
from .transport import RpcError
from .wire import Stream

EVENT_HISTORY_LIMIT = 20

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
        ("sys_events", identify.list_sys_events(EVENT_HISTORY_LIMIT), identify.decode_sys_events),
        (
            "user_events", identify.list_user_events(EVENT_HISTORY_LIMIT),
            identify.decode_user_events,
        ),
        ("saved_csf", identify.get_saved_csf(), identify.decode_saved_csf),
    )
    result: dict[str, Any] = {}
    for name, command, decoder in queries:
        try:
            body = await connection.rpc(*command)
            data = decoder(body)
        except RpcError as err:
            if err.path == command[0] and err.request_id is not None and err.stream == Stream.NONE:
                result[name] = {
                    "status": "unsupported" if err.code == 12 else "error",
                    "code": err.code,
                }
            else:
                # A status-stream error can interrupt an unrelated read.
                # It establishes nothing about support for this query.
                result[name] = {
                    "status": "error", "error_type": "RpcError",
                    "rpc_error": {
                        "request_id": err.request_id, "path": err.path,
                        "code": err.code,
                        "stream": err.stream.name if err.stream is not None else None,
                    },
                }
        except Exception as err:
            # A backend or decoder failure must not turn into a fabricated
            # zero-value snapshot, nor leak SSIDs/addresses in exception text.
            result[name] = {"status": "error", "error_type": type(err).__name__}
        else:
            if name in ("sys_events", "user_events"):
                # Bound retained history even if the peer ignores our limit.
                # Keep wire order: timestamp units and ordering are unproven.
                result[name] = {
                    "status": "ok", "data": data[:EVENT_HISTORY_LIMIT],
                    "received_count": len(data),
                    "omitted_count": max(0, len(data) - EVENT_HISTORY_LIMIT),
                }
            else:
                result[name] = {"status": "ok", "data": data}
    return result
