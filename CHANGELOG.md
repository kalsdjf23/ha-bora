# Changelog

## 0.1.0 — development draft, unreleased

- Independent Home Assistant integration with Bluetooth discovery, explicit
  pairing, configuration options, status streams and periodic reconciliation.
- Extraction, zones, settings and diagnostics based on the device descriptor.
  Controls default to off; cooking requires an additional option.
- Independent BRPC codecs, checksums, fragmentation, bounded RPCs and recovery
  without replaying control commands.
- Zone timer status in seconds, supported by application-code evidence;
  timer controls and stored-program reuse still require separate validation.
- Four concrete X PURE Assist programs from the anonymously readable catalogue,
  with local selection, a separate start button, exact default parameters and
  a fresh check for an idle, unbridged zone. No physical Assist trial performed.
- Separate Assist phase, confirmation indication and received target temperature
  for recognized programs, independent of the local selection.
- Supported filter replacement indication for known recirculation, without
  invented hours, percentages or a reset action.
- Explicit reads of stored Assist favorites, showing slot numbers, recognized
  titles and read time. The cache is invalidated on failure or disconnection.
- Bounded developer probe restricted to read methods, with redacted output.
- Bounded request tracing associates errors with an RPC and zone and records
  stream shutdown without raw error text.
- Transport errors retain the original RPC path, request ID and stream marker.
  Diagnostics redact these fields; a stream error is not misattributed to a
  status request that it interrupted.
- Diagnostic reports retain collected favorites after shutdown. Redacting
  absent numeric identifiers does not erase ordinary zero status values.
- Explicit connection/disconnection deadlines and checked reauthentication identity.
- Live cooking observation with confirmed zone/extraction levels and after-run.
  The resulting offline-tested fix isolates unavailable zones, preserves error/
  stream arrival order and rejects queued commands for unavailable zones.
- Central cooking-control checks and comparison of requested settings with
  readback, without automatic repetition when they differ.
- Sanitized recording fixtures, offline tests, HA runtime tests and prepared
  hassfest/HACS workflows.
- Initial private GitHub version with passing Linux CI: 720 tests, Ruff,
  dependency consistency and official hassfest. HACS validation remains deferred.
- Successful physical idle test of the report workflow. A separate fan trial
  returned code 12 without confirming control; subsequent independent reads
  confirmed extraction and every zone at 0. The exact failing RPC remains unknown.
- English project documentation, source code, interface text and GitHub material.

Source access is public; version 0.1.0 has no published release and has not
been submitted to HACS or installed on the user's Home Assistant system.
See [VALIDATION.md](docs/VALIDATION.md) for evidence and outstanding tests.
