"""Explicit, bounded developer probe. Importing this module performs no I/O."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.bora.ble import cooktop, extractor, identify, zone  # noqa: E402
from custom_components.bora.ble.client import BoraDevice  # noqa: E402
from custom_components.bora.ble.transport import (  # noqa: E402
    BrpcConnection,
    ConnectionLost,
    RpcError,
)
from custom_components.bora.ble.wire import FrameDecoder, Message, Stream  # noqa: E402
from custom_components.bora.diagnostics import async_get_config_entry_diagnostics  # noqa: E402

READ_PATHS = frozenset(
    command[0]
    for command in (
        identify.get_information(),
        identify.get_descriptor(),
        extractor.get_status(),
        cooktop.get_status(),
        zone.get_status("placeholder"),
        identify.get_wifi_status(),
        identify.get_heartbeat_status(),
        identify.get_heartbeat_period(),
        identify.list_sys_events(20),
        identify.list_user_events(20),
        identify.get_saved_csf(),
    )
)
STREAM_PATHS = frozenset((extractor.STREAM_PATH, cooktop.STREAM_PATH, zone.STREAM_PATH))
TRACE_LIMIT = 100


class ReadOnlyConnection(BrpcConnection):
    """Reject actuator, handshake-prompt and unknown RPCs at the probe boundary."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._trace = []
        self._trace_count = 0

    @property
    def request_trace(self):
        """Snapshot attempted exchanges, not proof of transmission or valid status."""
        return {
            "total": self._trace_count,
            "omitted": self._trace_count - len(self._trace),
            "requests": [dict(row) for row in self._trace],
        }

    async def _exchange(
        self, request_id, packet, *, wait_seconds=None, received=None, failed=None, path=None
    ):
        # Inspect our own framed request: never retain raw payloads, appliance
        # error text or backend exception messages in the export.
        message = Message(FrameDecoder().feed(packet)[0])
        request_path = message.text(2)
        self._trace_count += 1
        row = {
            "sequence": self._trace_count,
            "request_id": request_id,
            "path": request_path,
            "operation": (
                "stream_stop" if message.uint(6) == Stream.STOP
                else "stream_start" if request_path in STREAM_PATHS else "read"
            ),
            "started_at": datetime.now(UTC).isoformat(),
            "outcome": "pending",
        }
        if request_path == zone.GET_PATH:
            row["zone_uid"] = message.message(4).text(1)
        if len(self._trace) >= TRACE_LIMIT:
            self._trace.pop(1)  # Preserve the first exchange and the latest history.
        self._trace.append(row)
        try:
            reply = await super()._exchange(
                request_id, packet, wait_seconds=wait_seconds, received=received, failed=failed,
                path=path,
            )
        except asyncio.CancelledError:
            row["outcome"] = "cancelled"
            raise
        except Exception as err:
            row.update(outcome="error", error_type=type(err).__name__)
            if isinstance(err, RpcError):
                row.update(
                    error_code=err.code, error_request_id=err.request_id, error_path=err.path,
                    error_stream=err.stream.name if err.stream is not None else None,
                )
                # A stream failure can abort an unrelated waiting read. Keep
                # its true origin instead of inventing a response to that read.
                if err.request_id == request_id:
                    row["response_code"] = err.code
            raise
        else:
            # A reply can still fail the caller's stream/body validation.
            row.update(outcome="response", response_code=reply.code, stream=reply.stream.name)
            return reply
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()

    async def rpc(self, path, body=b"", *, received=None, failed=None):
        if path not in READ_PATHS:
            raise ValueError("This probe only permits known status/diagnostic reads")
        return await super().rpc(path, body, received=received, failed=failed)

    async def subscribe(self, path, callback):
        if path not in STREAM_PATHS:
            raise ValueError("This probe only permits known status streams")
        return await super().subscribe(path, callback)


def create_connection(address: str) -> ReadOnlyConnection:
    """Standalone tool only: runtime HA code keeps using HA's Bluetooth manager."""
    from bleak import BleakScanner
    from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

    async def connect(callback):
        device = await BleakScanner.find_device_by_address(address, timeout=10)
        if device is None:
            raise ConnectionLost("The requested appliance was not discovered")
        return await establish_connection(
            BleakClientWithServiceCache,
            device,
            "BORA read-only probe",
            disconnected_callback=callback,
            max_attempts=1,
            timeout=20,
        )

    return ReadOnlyConnection(connect)


async def observe(connection, *, address: str, seconds: int, pair=False, extended=False):
    """Return redacted evidence; never invoke a command or replay an update."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 <= seconds <= 300:
        raise ValueError("Observation duration must be 0 through 300 seconds")
    observations = []
    update_count = 0
    error_type = None
    optional_reads = {}

    def record():
        nonlocal update_count
        update_count += 1
        # Keep the first and the latest bounded history without unbounded RAM.
        if len(observations) >= 100:
            observations.pop(1)
        observations.append({"at": datetime.now(UTC).isoformat(), "state": device.snapshot})

    device = BoraDevice(connection, updated=record)
    try:
        # Includes initialization, observation and final reads. Disconnect has
        # its own deadline in BrpcConnection and also runs on cancellation.
        async with asyncio.timeout(seconds + 120):
            await device.initialize(pair=pair)
            record()
            await asyncio.sleep(seconds)
            if extended:
                # Keep the completed observation, independent of live caches
                # that shutdown correctly invalidates for HA entities.
                optional_reads = await device.collect_diagnostics()
            await device.refresh()
            record()
    except Exception as err:
        # Backend exception text can include private Bluetooth identifiers.
        error_type = type(err).__name__
    finally:
        await device.shutdown()
    export_device = SimpleNamespace(
        connection=connection,
        information=device.information,
        descriptor=device.descriptor,
        snapshot=device.snapshot,
        diagnostic_snapshot={
            "probe": {
                "status": "error" if error_type else "completed",
                "error_type": error_type,
                "observation_seconds": seconds,
                "status_updates_including_snapshots": update_count,
                "observations": observations,
                # Read after shutdown so stream STOP attempts are included.
                "request_trace": getattr(connection, "request_trace", None),
            },
            "optional_reads": optional_reads,
        },
    )
    entry = SimpleNamespace(
        unique_id=address,
        data={"address": address},
        runtime_data=SimpleNamespace(device=export_device),
    )
    return await async_get_config_entry_diagnostics(None, entry), bool(error_type)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True, help="Target Bluetooth address or macOS UUID")
    parser.add_argument("--output", required=True, type=Path, help="New JSON report file")
    parser.add_argument("--seconds", type=int, default=30, help="Observe for 0–300 seconds")
    parser.add_argument("--pair", action="store_true", help="Explicitly allow OS pairing")
    parser.add_argument("--extended", action="store_true", help="Also collect six optional reads")
    args = parser.parse_args()
    if not 0 <= args.seconds <= 300:
        parser.error("--seconds must be between 0 and 300")
    if args.output.exists():
        parser.error("--output must name a new file")
    if not args.output.parent.is_dir():
        parser.error("--output parent directory must already exist")
    connection = create_connection(args.address)
    report, failed = asyncio.run(
        observe(
            connection,
            address=args.address,
            seconds=args.seconds,
            pair=args.pair,
            extended=args.extended,
        )
    )
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("Redacted report written; connection closed locally.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
