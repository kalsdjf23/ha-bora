# Coverage of app and appliance features

This overview tracks the end goal: a broad local integration for ordinary use
in Home Assistant. It does not replace a hardware test. “Prepared” means
implemented and tested offline; the HA adapter and controls still need checking
on the real appliance.

## App features compared with the integration

BORA describes in its [app information](https://www.bora.com/en-int/products/products/supplies-and-accessories/app/joy)
an appliance-status overview, appliance metadata, Assist programs, and
personalising saved Assists. Recipe inspiration, user profiles, favourite
recipes, and the shop are also app features. That latter group is not local
cooktop control and does not belong in this BLE integration.

| Area | Local HA preparation | Work required for the full goal |
| --- | --- | --- |
| Status overview | Fan, zones, modes, residual heat, settings, and errors; separate Assist phase, confirmation notice, and known target temperature | Compare active zones and streams physically on HA |
| Standby and wake | Periodic status reads and reconnect when Bluetooth is reachable; no remote wake action | Distinguish panel-off reachability from later radio unavailability; identify an actual wake path before implementation; see [STANDBY.md](STANDBY.md) |
| Fan | Power, automatic/boost, after-run, and stop prepared; latest stop-only test attributed code 12 to `SetExtractorMode` for manual 0, with subsequent fan status still 1 | Establish accepted control paths; no successful control proven, older trial origin unresolved, latest manual shutdown confirmation pending; see [hardware checks](HARDWARE-CHECKS.md) |
| Cooking zones | Power, heat retention, automatic heat-up, pause, and stopping CSF | Confirm every control path with a user present |
| Timers | Codecs plus zone-timer duration, remaining time, and active status | Check setter units and actual start/stop operation |
| Settings | Locks, signal volume, touch sensitivity, pan detection, operating duration, and simple-mode features | Confirm meaning and support on this model |
| Start/change BORA Assist | Four concrete X PURE catalogue starts, local selection, and separate start button; exact parameters and checks prepared | Test physical operation/confirmation; support other programs and active modification |
| Saved Assists | Separate read button and sensors for slots 3–5; paired-Mac `GetSavedCsf` read returned built-in indices 1–2 only, consistent with an earlier app snapshot of three empty favorite slots | Validate populated favorites and real HA entities; test save semantics and retention of slots 1–2 before storage controls; snapshot comparison did not mutate favorites |
| Bridge zones | Bridge status and codec; the examined app selection retains two zones locally | Establish the actual BLE bridge/unbridge path and firmware behaviour |
| Filter status | Supported binary replacement alert for known recirculation; raw lifetime and types available | Establish BLE-status unit, reset meaning, and physical alert |
| Metadata | Model, versions, and redacted diagnostics | Check more models and first Linux pairing |
| Wi-Fi and events | Paired-Mac Wi-Fi and heartbeat-status reads succeeded; separate heartbeat-period query returned attributed code 5. Each event query returned 600 records; local cap retained 20 and counted 580 omitted | Validate HA diagnostic entities/cache and proxy use physically; event timestamp units and ordering remain unproven; see [diagnostic results](FEATURES.md#diagnostics) |
| Firmware | Version visible; no updater | Do not offer an update workflow as a generic write command |

## Additional behaviour from the manual

The official [X PURE manual, version 03](https://www.bora.com/product-documentation/operating-and-installation-instructions/umim-xpure-en.pdf)
describes an Assist start from the app with confirmation on the cooktop in
§7.4. A future HA action must retain that confirmation. §7.6 describes that
ending a program depends on the selected program. A sent request therefore
does not prove a completed cooking cycle.

This manual describes product behaviour, not BLE fields. For example, the
filter menu uses a percentage, whereas the [official filter information](https://www.bora.com/en-int/service/x-pure-v24)
states a nominal lifetime of about 150 operating hours for PUAKF. Neither
proves the unit of BLE field `remainingFilterLifetime` independently.

A separate app analysis now supports the warning at zero. The unit remains
unknown; see [FILTER-EVIDENCE.md](FILTER-EVIDENCE.md).

BORA’s [Data Act information sheet](https://www.bora.com/product-documentation/eu-data-act/bora_pure_range_data_act_information_sheet-en.pdf)
of 8 October 2025 names retrievable appliance data, but no available real-time
data offer. That alone is not a replacement for the local BLE status path. No
contact request or application was sent on the user’s behalf.

## Expansion limits

There is no arbitrary RPC service or reset, dealer, provisioning, or firmware
write button. Such methods are in the local research inventory, but must not
hide undocumented side effects behind an HA action. A missing or unrecognised
feature remains visibly open; a successful codec test alone is not marked as a
working appliance feature.

Public release, GitHub Releases, and HACS submission remain later work. The
new catalogue path uses captured metadata without a runtime account or cloud
request; see [ASSIST-PRESETS.md](ASSIST-PRESETS.md). See
[FEATURES.md](FEATURES.md), [VALIDATION.md](VALIDATION.md), and
[PUBLISHING.md](PUBLISHING.md) for the current implementation and test limits.
