# Viewing saved Assists

This preparation displays the three favorite slots used by the X PURE app:
**Saved Assist 3**, **Saved Assist 4** and **Saved Assist 5**.
The device metadata must identify X PURE and report a suitable index range.
This feature only reads data; it does not change the saved contents.

Press **Refresh saved Assists** to issue one `GetSavedCsf` request. The button
also works when general controls and cooking controls are disabled. Startup,
ordinary status checks and reconnection do not automatically read this list.
The existing **Refresh diagnostics** button already makes this request and
populates the same display without a second favorites request.

## Meaning of the display

| Display | Meaning |
| --- | --- |
| Unavailable | Not yet read, the read failed, or the connection is invalid. An empty slot is not assumed. |
| Program title | Both the reported program ID and type match one of the four known FRYING catalogue programs. |
| `unknown_<id>` | The slot is populated, but the ID/type pair was not recognized as a catalogue program. |
| `empty` | A successful read contains no parameters for this slot. |
| `ambiguous` | The response contains multiple parameter sets for the same slot. None is silently chosen. |

The `last_read` attribute gives the time of this local read in UTC, not a
timestamp from the cooktop. The received parameters remain visible as
attributes, without unproven timer or temperature conversions. The display
is a snapshot; changes made through the app require another read. The order
of the response list does not determine slot numbers: the code uses the
explicit `csf_index`.

A new read first removes the old values. After an error or cancellation,
they remain unknown. Disconnection, reinitialization and shutdown also clear
the display. A late response from an old connection must not repopulate it.
Downloading diagnostics uses only the data already available and generates
no appliance traffic.

## Starting and saving stored programs remain unavailable

A recognized title does not prove that its start parameters are safe. The
known discrepancy between saved and start timers, and the firmware's behavior
when saved slots are omitted, remain unresolved. This reading feature does
not fill in a local start selection or send `SaveCsf`, `StartOrModifyCsf`,
phase confirmation or a cooking zone change.

The app's save path and the unresolved question of preserving slots are
described in [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md). All tests of this display
have run offline; the first physical GetSavedCsf test has yet to take place.
