# Supervised hardware checks on 26 September 2026

These checks use the protocol client on an already paired Mac and one BORA
X PURE PUXU2R running BLE firmware 3.0.9. The user authorized the tests in
advance. They do not test the HA adapter, Linux pairing or a Bluetooth proxy.
Private reports are stored outside this repository.

## Attributed after-run stop failure

After the user confirmed that after-run was active, a separate bounded trial
tested the dedicated `StopAfterRun` method. An initial attempt could not
access Bluetooth from the restricted process; it sent no appliance command.
A discovery-only check with Bluetooth access succeeded, after which the
authorized trial connected once.

| Observation | Recorded value |
| --- | --- |
| First status read | 09:16:00.686 UTC; manual fan 1, 1,725,000 ms of after-run remaining |
| Second status read | 09:16:03.161 UTC; manual fan 1, 1,720,000 ms of after-run remaining |
| RPC | `/bora.generic.extractor.v1.ExtractorService/StopAfterRun` |
| Request body | Empty, as defined by the inspected schema |
| Requests for this control | Exactly one; no start, retry or reconnect |
| Response | 09:16:03.758 UTC; code 12 (`UNIMPLEMENTED`), request ID 3, exact `StopAfterRun` path, stream `NONE` |
| Error details | An Error object was present with an empty payload; no explanatory message |
| Cleanup | Connection closed at 09:16:03.758 UTC |

The two preflight reads established active after-run well above the trial's
one-minute threshold. The failed control phase performed no status readback;
neither a zero countdown nor physical silence was established. The user
subsequently chose to leave after-run running intentionally while remaining
present. No further appliance action was taken. Earlier manual shutdown
confirmations concern earlier trials only.

The dedicated after-run stop was rejected, separately from the earlier
manual-power-zero setter. This is not evidence that every write fails, and
does not test wake or the Home Assistant adapter. The private helper's nine
simulated-GATT scenarios cover acceptance, rejection, unchanged readback,
already-off/near-expiry preflight, lost reply, disconnect, read-only mode and
cancellation after transmission. They establish the helper's bounds and
reporting, not appliance support.

## Optional diagnostic reads

Before the dedicated `StopAfterRun` trial, a bounded read-only session used
the current protocol client with the six explicit optional queries. It
completed without an overall probe error
and closed the connection. Its trace contains 26 attempts with no omissions:
two metadata reads, three status subscriptions, two complete six-request
status rounds, six optional reads and three subscription stops. No pairing,
settings, heartbeat activation, fan or zone commands were sent.

| Optional query | Observed result |
| --- | --- |
| `GetWiFiStatus` | Code 0; status 17, labelled `iot_hub_connection_success` by the SDK enum |
| `GetHeartbeatStatus` | Code 0; request-active false, counter 0 and period 0 |
| `GetHeartbeatPeriod` | Code 5 on this exact unary RPC, request ID 14; retained as an error, not classified as unsupported |
| `ListSysEvents` | Code 0; 600 received records, 20 retained and 580 omitted by the local history limit |
| `ListUserEvents` | Code 0; 600 received records, 20 retained and 580 omitted; an unknown event type -1 remains `unknown_-1` |
| `GetSavedCsf` | Code 0; two entries with explicit indices 1 and 2; no entries for favorite slots 3 through 5 |

The event queries requested 20 records each; this firmware returned 600.
The local cap kept the exported histories bounded. Event timestamps, ordering
and the cause of the unknown event type remain unproven. Neither the debug
counters nor the period error establish a need to send heartbeat requests.
Wi-Fi status is the appliance's report, not an independent connectivity test.

The two saved entries correspond to the app's built-in slots; the absence of
3 through 5 is consistent with the three empty favorite positions in the
earlier app inspection. No saved program was changed to test persistence.
This verifies these reads on the paired Mac, not the HA button/entity path,
Linux, or a Bluetooth proxy.

Both status rounds still showed all four zones at 0 and the user's fan level
1. No automatic or manually confirmed fan-off is established by this session.
The private report and network identifiers remain outside the repository.

## Attributed fan-stop failure

The user manually set the fan to level 1 to keep the cooktop awake. A new
0 → 1 → 0 trial stopped at preflight because the fan was already at 1; it
sent no control commands. The stop portion of the agreed trial was then run
separately from the user's manually selected level 1.

At 07:06:39 UTC, preflight reported all four zones in manual power mode at
level 0 and the fan in manual mode at level 1. Exactly one control request was
sent:

| Field | Recorded value |
| --- | --- |
| RPC | `/bora.generic.extractor.v1.ExtractorService/SetExtractorMode` |
| Requested state | Manual power level 0 |
| Request body | `0a021000` |
| Error code | 12 (`UNIMPLEMENTED`) |
| Original error request ID | 12 |
| Original error path | The exact `SetExtractorMode` path above |
| Original error stream marker | `NONE` |

The error response arrived at 07:06:40 UTC. The failed setter phase performed
no readback, sent no ON request, and did not retry. The connection was closed
at 07:06:41 UTC. This run attributes the rejection directly to the setter;
it does not retrospectively identify the older trial's error source or prove
that every write is unsupported.

A separate read-only connection completed two full status rounds at
07:07:03 and 07:07:08 UTC. Both still reported fan level 1 and all four zones
at 0. It closed at 07:07:10 UTC. The user subsequently confirmed manually
stopping extraction, including after-run, with the panel off. This is a
physical user confirmation, not evidence of a successful remote stop.

An initial all-off report was corrected by the user because after-run was
still active. Reads at 07:34:23 and 07:34:30 UTC had returned fan level 1 and
an empty zone collection; they must not be labelled confirmed silent standby
or evidence of stale fan status. The corrected all-off confirmation was
recorded by 07:37:58 UTC for the subsequent discovery-only standby test.
No successful control action is established by these checks.
The [standby record](STANDBY.md) describes the subsequent disappearance from
two discovery windows and the unsuccessful bounded official Mac-app
connection attempt.

Before the manual shutdown above, the official app was connected for a
status-screen inspection.
It also displayed fan level 1 and four zone-zero indicators. The inspected
screen exposed the central fan value as an image in its status overview; no
manual fan-level control was identified there. This does not establish that
every app screen lacks such a control. No app control was activated, and
Disconnect returned the app to its visibly unconnected state.

A further static check confirmed the generic setter's path and body but
found no evidenced alternative X PURE route. A separately named extractor
protocol family in the SDK is insufficient reason to send its commands to
this appliance. The next step is to identify a real X PURE app control and
its caller path, if present, before another control experiment. The expanded
[fan-control investigation](FAN-CONTROL-INVESTIGATION.md) documents the
positively identified product route and the request-envelope check.

## Reading idle status

The report workflow in `scripts/readonly_probe.py` observed status for 60
seconds after initialization, without pairing, extended diagnostic requests
or controls. Both complete status rounds reported all four zones and
extraction in manual power mode at level 0.

The request trace contains twenty attempts, with no omitted rows:

- Two metadata requests and two complete status rounds of six requests each.
- Three status subscriptions with START acknowledgements.
- Three STOP acknowledgements during shutdown.

All twenty responses had code 0. The report finished with `completed` and no
error; the connection was locally closed after cleanup. The process ended
and no monitor remained running.

This confirms normal request tracing and the report workflow on the paired
Mac. Code 14 did not occur, so recovery from that specific firmware error
remains verified only offline. This test did not exercise `--pair`, optional
diagnostic requests or interrupted connections during the report workflow.

## Fan trial: first connection attempt

The device was unreachable during the first connection attempt for the
separately agreed 0 → 1 → 0 trial. Initialization ended with `ConnectionLost`
before the initial status check and before any control command. The client
was closed. This was not a successful fan trial and provides no new evidence
of physical control support.

## Fan trial after switching the cooktop on again

The connection succeeded after the user confirmed readiness. Initial status
reported all four zones and extraction in manual mode at level 0. The trial
allowed only known reads and `SetExtractorMode` for level 1 or 0.

The level-1 phase ended with RPC code 12 (`UNIMPLEMENTED`). The single level-0
shutdown phase also ended with code 12. No command was repeated, no zones
were operated and the connection was closed.

**This older trial's error is not conclusively associated with one RPC.** Its log
records phases without per-RPC paths or request IDs. The first phase includes
the write and an extraction status request; the shutdown phase includes the
write and the usual status requests. This establishes neither successful
control nor that `SetExtractorMode` itself returned code 12.

A separate read-only check immediately afterwards completed two full status
rounds with all four zones and extraction at 0, without errors. That connection
was also closed. This confirms the final state, not a successful shutdown command.

Static application analysis confirms the path and message structure for
manual levels 1 and 0. An advertised power mode and level list do not establish
support for the setter. This gap motivated the later attributed stop-only
test above; there is no basis for trying arbitrary payloads, handshakes or
unrelated controls.

The transport layer now retains the RPC path, request ID and stream marker
of the original error response. Diagnostics export this context without raw
error text. This is tested offline, including a stream failure that interrupts
another request. It does not add missing evidence to this older trial;
the later stop-only trial identifies the source only for that new run.

## Resumed trial with error attribution

The bounded trial helper now retains the original error path, request ID and
stream marker, including the connection's last RPC error when a stream failure
leaves a later operation with only `ConnectionLost`. Offline checks cover a
successful start/stop, rejected control requests and lost-connection cleanup.

The first physical attempt with this helper ended with `ConnectionLost`
before the initial status check. Its RPC trace was empty and it recorded no
RPC error response. No start or stop command was attempted, and the client
closed. This result does not identify the previous code-12 source or prove
that standby caused the connection failure. A later 0 → 1 → 0 attempt was
blocked by its fan-0 preflight requirement; the separate
stop-only result is recorded at the top of this document.
