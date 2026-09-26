# Bounded read-only probe for an agreed test session

`scripts/readonly_probe.py` is a development tool to use with the user present.
The CLI and report workflow have been tested with simulated peers. The
read-only connection class was used by a separate
[live cooking monitor](COOKING-OBSERVATION.md). The normal report workflow has
also been [physically run](HARDWARE-CHECKS.md) on the previously paired Mac.
That test did not cover pairing, extended diagnostics requests or error paths.

The tool explicitly connects to one specified Bluetooth identity, reads
metadata and status, follows the normal status streams for up to five minutes,
then writes a redacted JSON report. It closes the connection locally even on
error or cancellation. If the Bluetooth backend itself hangs, an interrupted
disconnect cannot guarantee a confirmed radio disconnection.

The RPC allowlist contains only known status and diagnostics requests.
Controls, firmware operations, resets and the separate user-confirmation RPC
are rejected. OS pairing is separate and disabled by default; `--pair`
explicitly permits it. This tool cannot start extraction or heating.

## Prepared commands

Run these only during an agreed physical test session. Use Python 3.14 and a
Bluetooth adapter on the machine running the command:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install bleak-retry-connector==4.7.0
.venv/bin/python scripts/readonly_probe.py \
  --address '<BLUETOOTH-ID>' --seconds 30 --output probe-status.json
```

For a new adapter, add `--pair` and confirm the normal pairing prompt on the
cooktop/host if it appears. Add `--extended` for the six optional diagnostics
requests. These include `GetSavedCsf`; an unsupported method is recorded as
such in the report. Always use a new filename. Existing files are not overwritten.

The report retains completed diagnostics requests after the connection has
closed and the live favorites cache has been cleared. Personal identifiers
and network addresses are redacted; a missing numeric address with value 0
leaves ordinary zero-valued settings, timers and program parameters intact.

`diagnostic_snapshot.probe.request_trace` records attempts with their sequence
number, request ID, RPC path and, for zone requests, zone UID. The outcome
contains only the response/error type and numeric error code, without a raw
response body or error text. For example, code 14 can be linked directly to
`GetZoneStatus(front_left)` without inferring that association from the polling
order. Stream starts and final STOP attempts appear in the same list. The
first and last attempts are retained, up to 100 rows; `total` and `omitted`
make missing intermediate rows visible.

A recorded attempt does not prove that all bytes reached the appliance.
`response` means the transport received a response; an invalid stream marker
or status body may still be rejected afterwards. `cancelled` and errors without
a response code are not assigned a fabricated appliance response. This trace
has been tested offline, including zone error code 14 and stream shutdown.
The physical idle test confirmed normal responses and stream shutdown;
zone error code 14 did not occur during that test.

An RPC error also retains `error_request_id`, `error_path`, `error_code` and
`error_stream`, which refer to the original error response. A stream error
can interrupt another pending status request. In that case, the interrupted
request does not receive a `response_code` as though it had received its own
error response. The diagnostics report also retains `last_rpc_error`, the
last known active RPC error with the same source context. This cache is empty
after reconnecting; downloading diagnostics makes no new appliance requests.

This is a standalone BLE test, not an HA installation or a Bluetooth proxy
test. The integration separately uses Home Assistant's Bluetooth manager.

## Specific open questions

- Compare a manually set zone timer with the duration/remaining time in the
  recording. App code supports milliseconds for these status fields.
- Compare the egg timer separately. A shared Protobuf type alone does not
  independently validate the readout or setter unit.
- Read saved Assists alongside the duration shown in the official app.
  The investigated save and start paths use different conversions for the
  same parameter field. A recording must establish what `GetSavedCsf`
  returns before a saved program can be reused.
- Compare filter status with the physical menu without resetting or writing
  values. A filter's nominal lifetime does not establish the unit of the
  remaining-lifetime field.

A status recording does not establish setter behavior. This tool therefore
sends no experimental control commands. Review the report before sharing it;
the export redacts known identifying data and excludes raw error text.
