# BORA for Home Assistant

An experimental, unofficial Bluetooth integration for BORA.
The integration includes status monitoring, extraction controls and cooking
settings, with controls disabled by default. Source code is available at
[kalsdjf23/ha-bora](https://github.com/kalsdjf23/ha-bora).
The project has no published release, has not been submitted to HACS, and has not been
validated with the cooktop on an actual Home Assistant installation.

Physical evidence covers one BORA X PURE, model PUXU2R with BLE firmware 3.0.9,
accessed from an already paired Mac. The Home Assistant integration has been
tested against recorded responses and simulated Bluetooth traffic. First-time
pairing on Linux, Bluetooth proxies, other BORA models and physical controls
through this integration remain unverified. See [validation and limitations](docs/VALIDATION.md).

A [live cooking observation](docs/COOKING-OBSERVATION.md) confirmed zone power,
extraction levels and the start of automatic after-run. A failure caused by a
temporarily unavailable zone was then fixed and tested offline; recovery from
that specific error still needs to be reproduced on the appliance.

Separate [fan stop trials](docs/HARDWARE-CHECKS.md) attributed code 12
(`UNIMPLEMENTED`) directly to both `SetExtractorMode` requesting manual
level 0 and the dedicated `StopAfterRun` method. Active after-run was read
before the latter request; it was not retried. No successful control is
proven. The oldest trial's code-12 origin remains unresolved; these newer
results do not establish that all writes are unsupported. The expanded
[fan-control investigation](docs/FAN-CONTROL-INVESTIGATION.md) records the
confirmed app route and remaining evidence needed.

## Prepared features

- Extraction level, automatic mode, an explicit boost preset, after-run duration and stopping after-run.
- Power, mode, residual heat, bridge status and cooking-program status for each
  zone, plus readable timer duration, remaining time and running state.
- Optional cooking controls: power, heat retention, automatic heat-up and stopping an active cooking program.
- Four X PURE Assist presets, with a local selection and a separate start button
  for each supported zone. Physical Assist confirmation is preserved. The current
  phase, required confirmation and recognized target temperature come from received status.
- Filter replacement indication for a known recirculation configuration, using the verified app threshold.
- Stored app favorites through an explicit refresh button and three status sensors.
- Pause, child lock, cleaning lock, signal volume, touch sensitivity and other supported settings.
- Device information, error codes and optional diagnostics collected only on request.
- Optional **Last reported Wi-Fi status**, with an explicit read time and no
  automatic Wi-Fi polling or network identifiers in its attributes.

Entities and choices follow the device descriptor and available status messages.
Not every model gets every feature. See [FEATURES.md](docs/FEATURES.md) for the
complete list, conditions and missing functionality. Zone timer status uses
verified millisecond conversions. Timer controls, egg-timer conversions and
filter units remain unresolved; see [TIMER-EVIDENCE.md](docs/TIMER-EVIDENCE.md).

The four catalogue starts and their evidence are documented in
[ASSIST-PRESETS.md](docs/ASSIST-PRESETS.md). These are prepared default starts;
custom parameters and reusing stored programs remain open work. The separate
[favorites overview](docs/SAVED-ASSISTS.md) provides read access without
starting or modifying stored programs.

The integration requires no cloud account and communicates locally over
Bluetooth. It uses Home Assistant's Bluetooth infrastructure, allowing different
adapters in the architecture without claiming that proxy pairing already works.

Automatic wake from standby is not currently supported. The integration can
reconnect when Bluetooth becomes reachable again; no verified X PURE wake
command has been found. See [standby and reconnection](docs/STANDBY.md).

## Enabling controls

Both options are disabled when the integration is added:

| Option | Meaning |
| --- | --- |
| Enable extraction and settings controls | Enables extraction controls and general settings. |
| Enable cooking controls | Additional permission for zone power, heat retention, automatic heat-up, pause and locks. Requires the first option too. |

Status entities and the optional diagnostics button remain usable with both
options disabled. Controls also require a reachable cooktop, valid status and
the relevant supported values. Missing status never becomes a zero level.
Reconnection restores reads and subscriptions; commands are never replayed
or queued for later delivery.

After a command is acknowledged, the integration reads status again and
compares the relevant field with the requested value. A differing or missing
value leaves the command unconfirmed while preserving the actual observed
state. The appliance may report a change later. A timeout can also leave the
outcome uncertain. The integration does not automatically repeat the command.

An explicitly attributed unsupported-action response leaves otherwise valid
monitoring available and reports that the requested action is unsupported.
A readback error, stream failure or uncertain response does not use this
exception. The command is not retried and other actions are not classified as
unsupported. Existing Assist protection against duplicate starts still applies.

## Future manual installation

Use the [supervised installation test guide](docs/INSTALLATION-TEST.md) for
prerequisites, backup, monitoring-only acceptance and scoped rollback.

These instructions describe a future, separately arranged test. They have not
been performed on the user's Home Assistant installation. Project metadata
requires Home Assistant 2026.9.3 or newer; the offline environment uses
2026.9.3 and Python 3.14. Older versions have not been validated.

1. Copy `custom_components/bora` to `/config/custom_components/bora` on the
   intended Home Assistant installation.
2. Restart Home Assistant and add **BORA** through **Settings → Devices & services**.
3. Select the discovered device or enter its Bluetooth identity manually.
   Setup asks you to activate Connect mode on the cooktop, close BORA One
   and confirm a pairing request if one appears.
4. Leave both control options disabled initially and check the displayed status.

First-time pairing with the chosen HA adapter still needs a physical test.
An existing Mac bond does not transfer to that adapter. Public release,
HACS installation and practical validation remain open;
see [PUBLISHING.md](docs/PUBLISHING.md).

## Development and tests

Protocol code is independent of Home Assistant under
[`custom_components/bora/ble`](custom_components/bora/ble).
The adapter, coordinator and entities connect that layer to Home Assistant.
Tests use fixtures and a simulated BLE peer; they never connect to the cooktop.

The latest local check passed **841 tests with 97% integration-code coverage**,
using Python 3.14.7 and the actual Home Assistant 2026.9.3 test runtime. Ruff
passed. Earlier official [hassfest validation](docs/HASSFEST.md), including
the requirements check, and [GitHub CI](docs/CI.md) also passed.
HACS validation and the physical HA installation test remain outstanding.

To create a Python 3.14 development environment:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

See [VALIDATION.md](docs/VALIDATION.md) for the scope and limitations of these
tests, and [PROTOCOL.md](docs/PROTOCOL.md) for the protocol description.
[APP-COVERAGE.md](docs/APP-COVERAGE.md) tracks the broader feature goal.
[READONLY-PROBE.md](docs/READONLY-PROBE.md) describes the bounded developer
probe. It has eighteen offline tests; its normal report workflow has also
been [tested physically](docs/HARDWARE-CHECKS.md) on the paired Mac.

The project uses the [MIT license](LICENSE). It is not an official BORA product
and does not distribute the official BORA application. Project documentation,
source code, interface text and GitHub material use English.
