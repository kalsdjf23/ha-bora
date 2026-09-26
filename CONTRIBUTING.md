# Contributing

This is an experimental development project on GitHub. Releases and HACS
submission remain deferred. Use Python 3.14; the pinned test environment uses
Home Assistant 2026.9.3.

Use English for documentation, source identifiers, comments, docstrings,
error messages, interface text, commits and GitHub titles/descriptions.
Keep protocol identifiers and original recorded evidence unchanged.

```sh
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
ruff check .
pytest -q --cov=custom_components.bora --cov-report=term-missing
```

Tests use selected recordings and simulated BLE connections. They do not
connect to a cooktop. Keep new tests independent of real hardware, adapters
and production Home Assistant installations as well.

Protocol code lives under `custom_components/bora/ble/` and does not import
Home Assistant. Preserve Protobuf field presence, descriptor limits and
unknown values; missing status must never mean a confirmed off state.
Control commands must not be automatically repeated, including after a timeout.

For each new feature, document these separately:

1. Source evidence for its path, message structure and units.
2. Capabilities advertised by the specific device.
3. Passing offline tests and any physical trial that was performed.

A physical control trial requires a present user and an agreed, bounded
scenario with verification of the final state. Do not leave a research
client or unbounded observation running. Firmware, reset and dealer actions
are outside ordinary Home Assistant controls.

Do not add official application files, access tokens, serial numbers, SSIDs,
host-specific Bluetooth identities or raw private scans. Use cached, redacted
Home Assistant diagnostics for a future issue report, and review the export
before sharing it publicly.
