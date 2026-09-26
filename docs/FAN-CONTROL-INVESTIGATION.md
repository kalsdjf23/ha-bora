# Investigating X PURE fan control

Manual fan control remains unverified on the tested X PURE PUXU2R running
BLE firmware 3.0.9. Two separate supervised operations received conclusively
attributed code-12 (`UNIMPLEMENTED`) responses: manual power zero through
`SetExtractorMode`, and the dedicated `StopAfterRun` method. Static
inspection confirms that the official app selects the same legacy service
family for X PURE, but has not identified a different supported fan-control
operation or an additional control-enabling handshake.

This note records evidence available on 26 September 2026. It does not
conclude that every write is unsupported, that all app versions behave the
same way, or that remote control or wake is impossible. The separate
[standby record](STANDBY.md) covers the repeated discovery and official-app
connection trial.

## Precisely attributed stop rejection

The user had manually selected fan level 1. A proposed 0 → 1 → 0 trial
stopped at preflight because the fan was already at 1; that attempt sent no
controls. A separate, authorized stop-only trial then checked that all four
zones were in manual power mode at 0 and the fan was in manual mode at 1.

| Field | Recorded value |
| --- | --- |
| Preflight time | 26 September 2026, 07:06:39 UTC |
| RPC | `/bora.generic.extractor.v1.ExtractorService/SetExtractorMode` |
| Requested state | Manual power level 0 |
| Request body | `0a021000` |
| Response time | 07:06:40 UTC |
| Response code | 12 (`UNIMPLEMENTED`) |
| Original response request ID | 12 |
| Original response path | The exact setter path above |
| Original response stream marker | `NONE` |

Exactly one control request was sent. The failed setter phase performed no
readback, sent no ON request and did not retry. The connection closed at
07:06:41 UTC. An independent read-only connection then completed two status
rounds, at 07:07:03 and 07:07:08 UTC, both showing fan 1 and all four zones 0.
It closed at 07:07:10 UTC. The request did not establish a successful stop;
the user subsequently confirmed stopping extraction and after-run manually.
That physical confirmation does not establish a successful remote stop.

The earlier trial logged code 12 by phase without identifying the original
RPC. Its phases included both a setter and status reads. The later result
does not retrospectively resolve that older error's origin. See
[the supervised hardware record](HARDWARE-CHECKS.md) for both histories.

## Dedicated after-run stop

A later trial tested `StopAfterRun` with its verified empty request, while
two fresh status readings showed manual fan 1 and more than 28 minutes of
after-run remaining. Exactly one stop request received code 12 at
09:16:03 UTC, with request ID 3, the exact method path and stream `NONE`.
Its Error object was present but empty, so the firmware supplied no further
explanation. The connection closed without retry or status readback; no
successful stop is established. See the [hardware record](HARDWARE-CHECKS.md)
for the preflight and cleanup evidence.

This tests a distinct method, not a different encoding of manual fan zero.
Its schema is established, but no high-level official-app caller was found
in the bounded static analysis. Neither result explains the firmware's
underlying reason or demonstrates a working fan-control alternative.

## Confirmed app route and limits of static analysis

Read-only inspection used BORA One 1.9.1, build 130922. The product factory
recognizes `ProductIdentifier.PureFamily.XPure`, constructs the
`PureFamily` device class derived from `LegacyBrpcDevice`, and installs
`bora.generic.extractor.v1.LegacyExtractorServiceImpl` with service name
`ExtractorService`. The higher-level cooktop repository also resolves this
same `PureFamily` class. This positively connects X PURE to the existing
generic route; it is more specific than finding an exported SDK method name.

The investigation narrowed several proposed alternatives:

| Candidate | Evidence and remaining limit |
| --- | --- |
| `c_sys.generic.extractor.v1.ExtractorService` | Generated interfaces, messages and bridges exist, but no implementing Kotlin class was found in this binary, and the X PURE factory does not install it. Its existence does not justify changing the namespace. |
| An unobserved manual fan caller | Bounded Kotlin interface-dispatch and Objective-C selector-reference scans found generated setter bridges, but no application-level manual fan call. The inspected cooktop repository exposes extractor observation, not a manual fan setter. Dynamic invocation, other code and other builds remain outside this negative result. |
| A connection authorization flag | The higher-level connection Boolean enforces an already-bonded device and otherwise raises `NotBondedException`. It is a local connection requirement, not a newly identified firmware authorization request. |
| ConnectionService or heartbeat setup | The inspected connection path and bounded dispatch scans supplied no positive evidence of an extra control-enabling request. Existing heartbeat/status methods do not, by their names alone, establish that prerequisite. |
| A settings-page control unlock | The examined device-settings model exposes rename/Wi-Fi options. Setter and `GetUserConfirmation` references examined through direct calls, interface dispatch and Objective-C selectors resolve to generated bindings or read streams; no concrete settings-write confirmation sequence or control-enable flag was established. This is not an exhaustive statement about every app screen or firmware prerequisite. |
| Missing request authorization headers | The shared request builder uses empty headers, client-stream `NONE`, and empty unknown fields. The unary fetch also uses server-stream `NONE`. The same request is serialized and framed downstream; no extra authorization header or replacement request was found in that inspected path. This narrows the envelope hypothesis, not every possible session prerequisite. |
| A generic “manual control” app action | The shared action emits a local navigation event. The concrete manual-control feature identified in the inspected metadata belongs to the cooking thermometer. The complete navigation branch was not reconstructed, so the label does not identify an X PURE fan action. |

The separately inspected official-app status screen displayed fan 1 and four
zone-zero indicators. No manual fan control was identified on that screen;
this was a status inspection, not an exhaustive review of every app screen
or a successful app control test.

## What the official documentation establishes

The [official X Pure manual, version 03](https://www.bora.com/product-documentation/operating-and-installation-instructions/umim-xpure-en.pdf)
includes PUXU2R and documents panel power and fan operation (§§5.3–5.4),
panel confirmation for app-transferred settings and Assist starts (§§6.4,
7.4), and persistent connectivity selection in the `Con` menu (§8.1).
It does not document remote manual fan adjustment or a wake command. It
also excludes a separate remote-control system from intended use (§2.1).
These are the manufacturer's documented operating constraints, not a
technical explanation of the observed code-12 response.

The [X Pure support page](https://www.bora.com/en-int/service/x-pure-v24)
advertises Assist, recipes and an appliance status overview. The
[official app listing](https://apps.apple.com/gb/app/bora-one/id1636501803)
listed version 1.9.1 when checked, matching the inspected app. Neither source
identified a manual fan command or remote-wake procedure in this review.
The manual covers multiple appliance revisions; no firmware-specific
explanation for BLE 3.0.9 was found.

Wi-Fi connectivity is a separate question. The successful diagnostic read
labelled `iot_hub_connection_success` reports an online connection while
the appliance was awake; it does not establish a cloud control API. BORA's
[Pure range Data Act sheet](https://www.bora.com/product-documentation/eu-data-act/bora_pure_range_data_act_information_sheet-en.pdf)
describes collected data and states that a real-time data offer is not
currently available. This does not rule out an internal app command channel.

The inspected high-level X PURE extractor-status flow resolves a managed
`PureFamily` device and invokes its legacy BLE stream. A bounded search of
cloud, direct-method, MQTT and network-device symbols found no concrete
alternative X PURE fan or wake transport. Device identifiers and IoT
provisioning code alone do not identify one. This static result does not
replace an independent physical iPhone test.

Panel-off Bluetooth reachability, a later unreachable radio, and the ability
to wake the main appliance are distinct. Normal reads and reconnects are
not evidence of wake. The known `clean_sys` `WakeUp` wrapper belongs to a
different product namespace. See [standby evidence and limits](STANDBY.md).

## Next discriminating evidence

A further fan-control experiment needs a positive source for an operation:
an actual X PURE fan action exposed by the official app, its caller and
transport path, or model-specific firmware documentation. With one client
connected at a time, identifying such an action would determine what to
trace. A separately agreed, supervised stop-only action with independently
observed panel and fan state could then distinguish a supported app route
from the already rejected request. App connection and status display alone
would not establish control support.

For a possible Wi-Fi wake path, a future supervised comparison can check
whether the official app obtains fresh status or visibly wakes the appliance
after ordinary Bluetooth reconnect fails, including a comparison with phone
Bluetooth disabled while the existing appliance Wi-Fi configuration remains
unchanged. Cached app state is insufficient evidence. Any successful case
needs its actual transport and operation identified before implementation.
The official Mac-app attempt is recorded separately; the iPhone Wi-Fi
comparison is not established by that Mac result.

The rejection's underlying cause remains unknown. The current evidence does
not justify substituting unrelated namespaces, inventing payloads, toggling
debug heartbeat, or treating a generic connection flag as a control unlock.
