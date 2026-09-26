# Future supervised Home Assistant installation test

This is a procedure for a future user-approved trial, not a completed
installation. No HA restart, deployment, pairing or appliance control was
performed while preparing it. Public source access and passing CI do not
establish physical HA compatibility or authorize this trial.

## Prerequisites to record before the trial

- Identify the target HA installation type, Core version, configuration
  directory and an existing approved way to access its files. Project metadata
  uses HA 2026.9.3 as the minimum; offline tests use exactly 2026.9.3. A newer
  version is a separate compatibility observation.
- Select an exact source commit or verified local package and record its
  SHA-256 from [PACKAGING.md](PACKAGING.md). A package predating a runtime
  change must not be described as testing that change.
- Confirm HA has a working Bluetooth integration and a connectable adapter
  within range. Passive advertisement reception alone is insufficient: BORA
  uses outgoing GATT connections. For Container installations, verify the
  host BlueZ and D-Bus setup against the [official Bluetooth
  requirements](https://www.home-assistant.io/integrations/bluetooth/#requirements-for-linux-systems).
  Proxy discovery alone does not establish BORA bonding support.
- Plan first pairing on the chosen HA adapter with the user at the cooktop.
  The existing Mac bond is not transferred. Close BORA One and other BORA
  clients for this test. First Linux/HA/proxy pairing remains unverified.
- Agree a short monitoring window and an HA restart window. The user manually
  powers the cooktop on with all zones and extraction off, and remains present
  to switch it off afterward. Do not start the fan just to prolong availability.

## Backup and scoped installation

Before changing files, create a backup including the HA configuration under
**Settings → System → Backups**. Keep a copy outside the HA machine and retain
the emergency kit needed for an encrypted backup. Follow the [official backup
procedure](https://www.home-assistant.io/common-tasks/general/#creating-a-manual-backup).
Record whether a BORA config entry or `custom_components/bora` directory already
exists, and preserve its prior contents separately before replacement.

During the approved window, copy only the chosen package's
`custom_components/bora` directory into the target configuration directory's
`custom_components/bora`. Verify that `manifest.json` sits directly inside
that directory, with no extra nested repository folder. This matches the
[official custom-integration layout](https://developers.home-assistant.io/docs/creating_integration_file_structure/#where-home-assistant-looks-for-integrations).
Do not copy research captures, tests or a development virtual environment.

Restart HA only as agreed, then add **BORA** through **Settings → Devices &
services**. Select the discovered appliance or its target-adapter Bluetooth
identity. Follow the explicit pairing confirmation step and the appliance's
Connect prompt. Leave both extraction/settings and cooking-control options
disabled. If discovery or pairing fails, retain the error and stop rather
than resetting bonds, changing adapter configuration or trying controls.

## First acceptance: monitoring only

Record the commit/package, HA version, adapter model/backend and outcomes
locally, without publishing host identifiers or unredacted diagnostics.

| Check | Expected observation |
| --- | --- |
| Initial setup | One BORA entry loads; reported model and zone identities match the appliance. |
| Idle status | All four zone levels and fan level agree with the user's panel observation; absent status remains unknown, never fabricated zero. |
| Guard settings | Both control options remain disabled; no automation or control action is used. |
| Explicit optional reads | If included in the agreed scope, press a read-only refresh button once; distinguish query errors from core-status failure and inspect sanitized diagnostics. |
| User panel-off/on | Record Bluetooth availability and any transition to unavailable. After manual panel-on, check fresh status recovery without a queued or replayed command. Remote wake is not an acceptance criterion; see [STANDBY.md](STANDBY.md). |
| End of session | User confirms the physical final state. Removing an entry or closing Bluetooth does not switch the appliance off. |

A successful result applies only to this HA version, adapter, appliance and
firmware. It does not validate cooking or extraction writes. Those require a
separate bounded scenario; the attributed fan-stop rejection remains recorded
in [HARDWARE-CHECKS.md](HARDWARE-CHECKS.md).

## Rollback if the trial fails

Remove only the trial's BORA integration instance through **Settings → Devices
& services → BORA**, using the entry's menu and **Delete**, following the
[official removal procedure](https://www.home-assistant.io/common-tasks/general/#removing-an-integration-instance).
Then remove only the trial's `custom_components/bora` directory, or restore
the saved previous directory if one existed, and restart HA in the agreed
window. Do not delete other integrations, edit `.storage` directly, reset
Bluetooth bonds or factory-reset the cooktop as routine cleanup.

If HA cannot start, use the previously agreed file-access method to undo that
directory change. A full configuration restore can overwrite unrelated changes;
reserve it for an explicitly chosen recovery using the [official restore
procedure](https://www.home-assistant.io/common-tasks/general/#restoring-a-backup).
No rollback action has been executed by preparing this document.
