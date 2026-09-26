# Supervised hardware checks on 26 September 2026

These checks use the protocol client on an already paired Mac and one BORA
X PURE PUXU2R running BLE firmware 3.0.9. The user authorized the tests in
advance. They do not test the HA adapter, Linux pairing or a Bluetooth proxy.
Private reports are stored outside this repository.

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

**The error is not yet conclusively associated with one RPC.** The trial log
records phases without per-RPC paths or request IDs. The first phase includes
the write and an extraction status request; the shutdown phase includes the
write and the usual status requests. This establishes neither successful
control nor that `SetExtractorMode` itself returned code 12.

A separate read-only check immediately afterwards completed two full status
rounds with all four zones and extraction at 0, without errors. That connection
was also closed. This confirms the final state, not a successful shutdown command.

Static application analysis confirms the path and message structure for
manual levels 1 and 0. An advertised power mode and level list do not establish
support for the setter. The next targeted test needs to associate the error
with its exact RPC; there is no basis for trying arbitrary payloads, handshakes
or unrelated controls.

The transport layer now retains the RPC path, request ID and stream marker
of the original error response. Diagnostics export this context without raw
error text. This is tested offline, including a stream failure that interrupts
another request. It does not add missing evidence to the previous trial;
a new physical test is still needed to identify the source of code 12.
