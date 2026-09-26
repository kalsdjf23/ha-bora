# Validation and open evidence

Status of local preparation: 26 September 2026. The current HA code has been
tested offline. This integration has not yet been physically validated on Home
Assistant, Linux, or a Bluetooth proxy, and its control commands have not been
physically validated successfully. The latest stop-only trial attributed code
12 directly to `SetExtractorMode` for manual level 0; subsequent independent
reads still showed fan 1 and all four zones 0. Manual shutdown confirmation
is pending in this record. See [the hardware checks](HARDWARE-CHECKS.md).

## Different kinds of evidence

| Level | What it supports | What it does not prove |
| --- | --- | --- |
| Static schema and application-code analysis | RPC paths, field numbers, field types, enums, message construction, and explicit conversions from BORA One 1.9.1, build 130922. | That every method exists on every appliance, or that an examined conversion also applies to other fields. |
| Public program catalogue | Anonymous HTTP 200 response with four concrete X PURE program IDs, target values, limits, and settings, connected to the statically examined app mapper. | Firmware acceptance, temperature control, or physical confirmation. |
| Earlier device captures | Valid responses and observed changes from one X PURE through a paired Mac. | First pairing on another host, every mode, write actions, or long-term reliability. |
| Offline codec, transport, and HA tests | Implementation behaviour against fixtures, simulated responses, and error cases. | Real Bluetooth encryption, radio connectivity, hardware, or firmware operation. |
| Physical integration trial | Still to be performed on the target HA installation. | Until that trial is complete, HA/Linux/proxy support is not proven. |

## Existing physical observations

Research appliance: BORA X PURE PUXU2R, BLE firmware 3.0.9. The Mac had
previously been paired. Standalone status queries and status subscriptions
were then tested with the official app disconnected. During the initial
captures below, the user changed appliance settings themselves; the research
client did not send start commands.

- Fan levels were both queried and followed through a status stream, with
  levels 3 and 5 manually confirmed. A sequence of separate queries received
  separate responses.
- On 25 September, the appliance descriptor, cooktop status, and the status of
  all four zones were read. The captured zones were off. This does not prove a
  heating mode or pan detection.
- The raw after-run counter dropped by about 5,000 units in five seconds. This
  supports milliseconds for `remainingAfterRun`. The evidence does not
  automatically apply to other timer or filter fields.
- The previously paired Mac could later reconnect without pairing again. First
  pairing with the new Python/HA client is not proven.
- A stream could start and stop without an intervening status message. The
  implementation therefore explicitly requests an initial snapshot.
- A short session of more than three minutes worked without a separate
  application heartbeat. This is not a long-term test. Unreachability after
  idle time was observed; the precise sleep and wake rules remain unknown.

On 26 September, the standalone Python client also monitored the appliance
during cooking. The user confirmed back-left level 7 and fan level 3; the
transition to zone 0 and a 30-minute after-run were received. The capture
contains 93 CRC-valid responses and revealed an error for temporarily
unavailable zone status. The resulting correction was tested offline, but has
not yet been trialled with a new code-14 observation. See [the cooking
observation](COOKING-OBSERVATION.md).

The latest [stop-only trial](HARDWARE-CHECKS.md) began after the user manually
set the fan to 1. The initial 0 → 1 → 0 attempt aborted at preflight without
sending a control. The agreed stop was then tested separately: it read all four zones
at 0 and sent exactly one `SetExtractorMode` request for manual level 0, body
`0a021000`. Its code-12 response carried request ID 12, the exact setter path,
and stream marker `NONE`. No ON request or readback occurred in the failed
setter phase, and the connection closed. A separate read-only session then
completed two full rounds showing fan 1 and zones 0 before closing. The user
was asked to stop the fan manually; no confirmation has been recorded yet.
This establishes a rejected setter for this run, not universal write failure.

Earlier [idle and fan-control trials](HARDWARE-CHECKS.md) used the protocol
client. Normal status reads, request logging, and stream closure succeeded.
The earlier 0 → 1 → 0 trial returned code 12 in both control phases; the
write or read-back RPC that caused it was not logged directly and remains
unresolved. Its separate follow-up read reported all four zones and the fan
at 0. That historical result must not be confused with the latest fan-1
readings. No successful control action is proven by either trial.

The original research notes and private captures remain in a separate local
research archive. That archive and the official app binary are not part of
this distribution. The standalone [protocol description](PROTOCOL.md)
summarises the relevant evidence. The repository contains a
[fixture with captured protocol data](../tests/fixtures/x_pure_3_0_9.json)
for reproducible offline checks.

The subsequent [optional diagnostic trial](HARDWARE-CHECKS.md) completed all
six queries on the paired Mac. Wi-Fi status, debug heartbeat status, both
event lists and saved CSF parameters returned code 0. The separate heartbeat
period query returned an attributed code 5 without interrupting the later
reads. Both event lists contained 600 records; the collector retained 20 from
each and recorded 580 omissions. The saved list contained built-in indices
1 and 2, with no entries for favorite slots 3 through 5. These results verify
the standalone reads, not a physical HA entity or a saved-program write.
The session sent no controls and ended with the connection closed; status
still showed fan 1 and all four zones 0.

## Additional evidence for zone-timer status

The app explicitly converts `ZoneStatus.settings.timer.duration` and
`remaining` using Kotlin `MILLISECONDS`. The zone sensors therefore show
duration and remaining time in seconds; the running flag has a separate binary
sensor. The raw timer data remain available. This is static evidence from
application code, not a new physical timer trial.

In addition, one concrete default start for four catalogue programs has been
reconstructed. The app writes index 0 and timer 0; the complete data path was
traced, including the hidden timer screen and the selection of one zone. This
allows a limited start implementation without copying saved-program
parameters. See [ASSIST-PRESETS.md](ASSIST-PRESETS.md) for the source,
settings, and limits.

The units and limits of ordinary timer setters, the separate cooking timer,
and filter units remain unknown. A CSF difference has also been established:
saving writes seconds without conversion, whereas starting converts to
milliseconds. Firmware behaviour during save/read-back remains unknown. See
[TIMER-EVIDENCE.md](TIMER-EVIDENCE.md) for the concrete evidence and limits.

A new filter analysis traces the app boolean `shouldChangeFilter` back to
`remainingFilterLifetime < 1` and forward to the Swift warning. This supports
a binary replacement alert without establishing its unit. The integration
limits it to explicit recirculation and ordinary positive Int32 values or
zero; other cases remain unknown. See
[FILTER-EVIDENCE.md](FILTER-EVIDENCE.md).

## Platform status

| Environment | Status |
| --- | --- |
| Previously paired Mac, research client | Physical read-only trial succeeded for the stated functions. |
| Home Assistant 2026.9.3, Python 3.14 | Offline test environment with simulated Bluetooth connectivity. |
| Linux / BlueZ with local adapter | Adapter path implemented; first pairing, bond storage, and physical use are not yet proven. |
| Bluetooth proxy, including ESPHome | Not physically validated. Ordinary GATT notify/write support does not prove support for the necessary bonding and encryption. |
| Other models or firmware versions | Not physically validated; descriptor support alone is insufficient evidence. |

A Bluetooth bond belongs to the identity of the host/adapter. A Mac bond does
not move to Linux or a proxy with this code. The configuration has an explicit
pairing step and reauthentication path; their existence does not prove that
every backend performs and retains that pairing.

## What the offline tests check

The latest complete local run produced **841 passing tests** and **97% coverage**
of the integration code (2,364 statements, 80 missed). The
[package checks](PACKAGING.md) also run the current suite against the extracted
runtime and distinguish earlier archives from the current candidate.
Testing used Python 3.14.7 and the real Home
Assistant 2026.9.3 runtime, while the Bluetooth peer remained simulated. The
fixtures include 39 earlier sanitised responses and four selected payloads
from the cooking observation. Ruff reported no errors. The official Home
Assistant hassfest validator passed again, including `--requirements`, with
zero invalid integrations and zero warnings, against core 2026.9.3, commit
`6de5eb18cd4502f94af44cfff3a02250d88716ed`. The new abort translation for a
mismatched reauthentication identity was included in this validation. The
[hassfest report](HASSFEST.md) contains the reproducible command.
The first three private GitHub runs also succeeded on Ubuntu 24.04/Python
3.14.7; the documented run had 720 tests, 96% coverage, Ruff, dependency
checking, and the official hassfest action; see [CI.md](CI.md). The official HACS validator has
not run. Its
[entrypoint](https://github.com/hacs/integration/blob/main/action/action.py)
requires a GitHub token and repository name; its
[repository code](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py)
reads GitHub metadata and files, not just a local integration directory. The
source repository has been authorized for public access, while HACS validation,
submission and releases remain deferred. See
[publishing preparation](PUBLISHING.md) for sources and requirements.
Hassfest, offline tests, and package checks are not substitutes.

The configuration flow now has 100% statement coverage. That is not a claim
of completeness: the Bluetooth backend is simulated, and first physical
pairing and backend-dependent behaviour need further tests.

The [tests](../tests) cover, among other things:

- Framing, checksums, fragmentation, Protobuf presence, enums, and descriptor
  limits.
- Decodable captured messages and unknown or invalid fields.
- Request IDs, stream lifecycles, timeouts, broken connections, and late
  callbacks; ordered status updates for concurrent queries and streams.
- A stream failure interrupting another setup/read does not establish that
  the interrupted method is unsupported. Reinitialization closes the previous
  connection before rebuilding subscriptions, excluding old same-path streams.
- New initial snapshots, subscription recovery, optionally unsupported methods,
  and not replaying control commands after reconnect.
- Both control options, validation of zones and levels, no fabricated zero
  values, confirmation by read-back, and correct availability.
- A directly attributed unary code-12 rejection of the expected setter leaves
  already-valid monitoring available on a live connection. It reports the
  requested action as unsupported without publishing a new status, replaying
  the command or blacklisting other actions. Unknown origins, stream failures,
  failed readback, timeouts and lost availability retain the failure path.
- Central cooking safeguards for locks, pan detection, maximum operating time,
  and the simple-mode group, including when an internal caller omits the
  cooking flag.
- Acknowledgement with differing or missing read-back: no success claim, no
  repeated write command, retention of real status, and processing of a later
  stream update where present.
- Not deriving fixed heat-retention control from the mode enum alone when
  variable support is absent; the three known modes remain possible when the
  descriptor advertises them through that support.
- Discovery without automatic pairing, configuration, reauthentication with
  confirmation, success, errors, explicit retry, and appliance identity checks.
- Both options and reloading changed settings; probe cleanup on success, error,
  timeout, and cancellation, plus unload/shutdown and dynamic entities. The
  limited trial logging connects a zone error to the request-ID/RPC path and
  retains stream closure without raw error text or a fabricated response.
- Zone timers: conversion of 33,000 milliseconds to 33 seconds, retaining
  fractions and raw data, the correct zone, and missing timers without a
  fabricated zero state.
- Atomic merging of simple-mode settings and read-only diagnostics, including
  redaction and downloading without new appliance requests.
- Namespace-specific names for system/user events, unknown numeric types,
  raw timestamps, duplicate entries and wire order; local retention of at most
  20 records per list with received/omitted counts even if the peer ignores
  the requested limit. These checks do not establish time units or live faults.
- The optional last-reported Wi-Fi sensor through actual HA services and a
  simulated peer: disabled registry defaults, explicit reads with controls off,
  distinct/unknown statuses, no network identifiers or automatic queries,
  exact response timestamp, and invalidation on failure, cancellation,
  disconnect, reconnect and reload. A late cache failure clears both Wi-Fi and
  saved-Assist display results, including their diagnostic copies.
- Assist selection without I/O, explicit start, a fresh off-state check,
  rejection of active/bridged zones and differing preset parameters, repeated
  presses without altering a running program, and no replay after reconnect.
  The `confirmation-required` phase remains visible.
- The actual HA services for Assist selection/start and HA status transitions
  for phase 2, an unknown phase, phase 3, and program completion, with a fake
  BLE peer. The received target temperature and program title do not change
  through another local selection. No default temperature is supplied for
  missing data.
- Filter alerts for zero, ordinary positive values, unknown or exceptional
  values, recirculation versus extraction, and loss of connection/status.
- Saved favourites: explicit reads only, slot number rather than list order,
  recognition without assuming units, duplicate indexes, the difference
  between unknown and a successful empty response, errors/cancellation, cache
  loss on disconnect, and rejection of late responses.
- A temporarily unavailable zone (code 14): only that status becomes unknown;
  other sources remain usable. Correct error/stream ordering, no successful
  refresh after disconnect, and no waiting zone write after invalidation.

Assist starts have an additional recovery boundary: concurrent requests for
the same zone are excluded before waiting for the connection. A possibly sent
start remains blocked after an error, cancellation, or reconnect until a later
received status shows precisely that program in `preheat`,
`confirmation-required`, or `active`. An off state does not lift the block,
because delayed application remains possible. If the program is never
applied, the block can therefore remain for the current client instance. It
is not persisted across integration reload or HA restart. This conservative
policy does not prove actual firmware timing; recovery after an uncertain
physical start still needs validation.

The separate [read-only tool](READONLY-PROBE.md) has eighteen offline tests in
this test suite: allowed reads, rejection of control and confirmation commands
before I/O, time limits, redacted output, and cleanup on cancellation or
error. The optional saved-favourites read remains in the report after closure,
including for an empty or unsupported response. The diagnostics tests also
check that a numeric default address of 0 does not clear zero values in normal
status; real numeric identifiers and their aliases remain redacted. The
CLI/report workflow completed a physical 60-second read-only run; its
read-only connection class was also used in the cooking monitor. Its extended
optional-query workflow has now run physically as described above. Pairing
and interrupted connections in that workflow remain offline-only. These
standalone BLE trials are not HA or proxy tests.

Run from the project directory with a prepared development environment:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

These commands test local code; a green result is not hardware certification.
The minimum version in metadata is the offline-tested version 2026.9.3; older
versions have not been validated.

## Still to validate physically

Every item below remains open for a later agreed trial with someone present at
the appliance. They were not performed during this preparation.

- [ ] First pairing on the target HA adapter, including physical Connect mode,
  encrypted characteristics, restart, and bond retention.
- [ ] Compare read-only status and subscriptions on HA with the control panel.
- [ ] Test range loss, sleep/wake, recovery, HA restart, and longer
  connections; establish whether a heartbeat is ever needed.
- [ ] Repeat the code-14 correction during after-run physically: the fan
  remains visible, missing zones are unknown, and they recover on valid status.
- [ ] Check present and missing values for active zones, residual heat, pan
  detection, bridge status, and CSF phases.
- [ ] Confirm supported controls separately, including read-back, error cases,
  and the descriptor values actually offered.
- [ ] Compare the supported zone-timer status conversions with a manually set
  timer.
- [ ] Establish setter units and limits for timers, the separate cooking timer,
  filter fields, and CSF save/start conversions before additional controls.
- [ ] Test the four prepared Assist starts and physical confirmation on the
  cooktop, including the actual final state after stopping.
- [ ] Compare the filter-replacement alert with the real app; raw scale and
  reset behaviour remain separate research questions.
- [ ] Test SaveCsf persistence semantics using complete lists before and after
  a deliberate app change, including omitted slots and retention of slots 1–2.
- [ ] First compare the read-only saved-favourites button and slots 3–5 with
  the official app, without writing saved parameters back.
- [ ] Reconstruct and validate bridge/unbridge behaviour, other CSF starts,
  and active modification before further expansion.
- [ ] Test any proxy support for each concrete hardware/software combination
  and update the support matrix.

For current feature choices and limitations: [FEATURES.md](FEATURES.md).

## Assessment of the full end goal

Local preparation is not the same as a working, fully tested first release.
The assessment below uses current code and existing evidence; missing evidence
is not counted as a successful check.

| Requirement | Current evidence | Assessment |
| --- | --- | --- |
| Installable HA/HACS project structure | Configuration flow, seven entity platforms, manifest, HACS metadata, icon, licence, and workflows; local hassfest passed. | Prepared locally; actual installation and HACS validation remain open. |
| Local connection without a cloud account in the integration | Standalone BRPC layer, adapter code, and earlier Mac status captures. | First HA pairing, bond retention, and proxy behaviour are not proven. |
| Broad usable app and BLE functionality | Supported status, fan, zones, four catalogue starts, Assist phase/target/confirmation, saved-favourites overview, filter alert, settings, and optional diagnostics; inventory of 54 generated generic RPCs examined. | Incomplete: timer control, other CSF starts/modification/storage, bridge, and filter units/reset remain open. |
| Reliable control and recovery | Offline tests for limits, read-back, timeouts, streams, cancellation, and no command replay. | Software behaviour tested; appliance responses, timing, and endurance trial are missing. |
| Tests, documentation, and usable first release | Reproducible offline suite, captures, protocol and feature documentation, read-only trial script. | Preparation exists; physical acceptance and final release choices are missing. |
| Release and HACS submission later | Source uploads and public repository access authorized; metadata and workflows prepared. | Releases, HACS validation and submission remain deferred at the user's request. |

The next necessary external step is a trial with a user present at the target
HA adapter, initially with both control options disabled. Focused comparisons
with the official app are also required for still-unknown timer, preset, and
filter values. Rerunning the already successful offline suite cannot replace
these missing observations.
