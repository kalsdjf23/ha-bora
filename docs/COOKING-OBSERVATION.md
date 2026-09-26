# Cooking observation on 26 September 2026

The user asked for monitoring while cooking and subsequently confirmed the
back-left zone at level 7 and extraction at level 3. The standalone Python
client observed the appliance from an already paired Mac for about six minutes.
It used the integration's protocol code with an allowlist of status requests,
three status subscriptions and periodic reads. No settings were changed,
no pairing was performed and no commands were sent to Home Assistant.

## Observations

| Event | Received data |
| --- | --- |
| Initial state | All four zones and extraction at 0. |
| Cooking | Back-left changed through 3 to 7; extraction changed through 4 to 3. The user confirmed zone level 7 and extraction level 3. |
| After-run started | Extraction at 1 with 1,800,000 ms remaining: 30 minutes. |
| Zone switched off | Back-left explicitly reported power 0, about six seconds after after-run began. |
| Countdown | After-run decreased by 5,000 ms about every five seconds, reaching 1,760,000 ms in the last observed stream update. |
| Read failure | A zone status request received code 14 (`UNAVAILABLE`) after extraction and cooktop status had been read successfully. |
| Shutdown | All three status subscriptions were stopped and Bluetooth was disconnected. The user confirmed that the cooktop was off with after-run active and asked to end the observation. |

The recording contains 93 responses with valid CRCs, including 16 actual zone
and extraction stream updates. The cooktop stream started but produced no
CONTINUE message during this observation; cooktop status came from periodic
requests. No message provided positive evidence of residual heat. No temperature
measurement or timer, Assist or bridge controls were tested. After-run was not
observed all the way down to zero.

Four sanitized response payloads are included in
[the cooking fixture](../tests/fixtures/x_pure_cooking_2026_09_26.json).
Device identifiers, system information and private recordings are excluded.
The known request order associates the error with `GetZoneStatus(front_left)`;
the recording does not contain transmitted RPC paths. The exact firmware cause
remains unknown.

## Resulting fix

The previous client allowed a zone status error to abort the entire refresh.
The new handling marks only the affected zone as unknown after a valid unary
code 14 and continues reading other sources. Unknown does not become off.
A later valid zone status message can make that zone available again.

Failure and recovery are processed in arrival order, so a waiting error handler
cannot erase newer stream status. A real disconnection remains an error, even
immediately after the final response. Other RPC errors, invalid messages and
timeouts retain their existing behavior.

Zone controls check for current zone status under the same lock. A queued
command therefore cannot operate a zone that has become unavailable while
it was waiting. Missing readback does not confirm a command.

This fix has been tested offline, including HA coordinator/entity behavior,
both message orders and connection loss. A later separately authorized
[read-only test](HARDWARE-CHECKS.md) using the updated client completed without
errors. **Code 14 did not recur in that test:** recovery from this specific
error remains verified only offline. This does not establish HA/Linux pairing,
proxy support or physical control-command support.
