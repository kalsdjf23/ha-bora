# BORA Local integration

This is a preparation project. The user authorized creating and pushing to
the private GitHub repository kalsdjf23/ha-bora. Keep it private. Do not create
releases, make the repository public, submit HACS requests, or deploy to the
user's Home Assistant without a new instruction.

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
