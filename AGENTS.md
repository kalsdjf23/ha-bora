# BORA Local integration

Use English for all project documentation, source identifiers, comments,
docstrings, error messages, user-facing strings, commit messages, and GitHub
titles/descriptions. Keep protocol identifiers and recorded evidence intact;
do not translate wire values or change fixtures merely to rename source data.

This is a preparation project. The user authorized uploading to
kalsdjf23/ha-bora and making the repository public after the English-language
review and validation. Releases, HACS submission and deployment to the user's
Home Assistant still require a separate instruction. Public source access
does not establish release readiness or HACS approval.

Default testing uses recordings and a simulated BLE peer. Real appliance
tests require an agreed, bounded session with the user present. The user
authorized a new read test on 26 September 2026 and offered permission for
controls; agree a concrete control scenario and verify its final state before
using that permission. Never leave heating or extraction running unattended.

Keep protocol/transport independent of Home Assistant under
custom_components/bora/ble. No raw-command HA service. Reconnection must
only restore reads/subscriptions, never replay control commands. Derive
commands from verified descriptors, not guesses. Device support and units
need separate evidence from the existence of an RPC name in the app.

Do not include the official application, account information, host-specific
identifiers, or unsanitized Bluetooth scans in the future release.

Record feature coverage and remaining physical verification in docs. A
passing simulated test is not proof of hardware support. The final objective
is broad useful app/BLE feature coverage, not a read-only-only integration.
