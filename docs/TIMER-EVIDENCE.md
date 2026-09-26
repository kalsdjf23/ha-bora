# Evidence limits for timers and cooking programs

Additional offline analysis of BORA One 1.9.1, build 130922. This document
describes independent findings from application code, not recordings of
new control tests.

## Proven conversions

| Field or use | Evidence | Use in HA |
| --- | --- | --- |
| `ZoneStatus.settings.timer.duration` and `remaining` | The Pure CPC mapper `toCPCAssistFunction` reads both fields and calls `toDuration(Int, MILLISECONDS)`. | Display zone status in seconds; retain the raw data. |
| `CsfParameter.csfTimerDuration` when starting | The preset start path converts the selected seconds through `inWholeMilliseconds` and writes field 11. | Evidence for this start parameter, not a general statement about every timer RPC. |
| `remainingAfterRun` | Earlier physical countdown recordings. | Remaining after-run time in seconds. |

The zone timer conversions are at arm64 addresses `0x101448624` and
`0x1014486a0`; the preset path is at `0x10130ac68–0x10130ad08`. The object
fields were checked against the Timer, ZoneSettings and ZoneStatus
constructors and the actual Kotlin DurationUnit objects. A matching name
or plausible value alone was not accepted as evidence.

The units of ordinary `SetTimer` and `SetEggTimer` requests, timer limits,
the separate use of the egg timer and filter units still need independent
evidence. They are not automatically inferred from a status field.

The separately inspected `SetTimerState` and `SetEggTimerState` messages
also do not yet establish start/pause/resume behavior. Their boolean can be
sent without a duration field, but no app call was found that establishes
whether the remaining time is preserved or cleared. A pause/resume button
is therefore not inferred from the field names alone.

## Why saved Assists cannot yet be started

The start workflow uses a catalogue program ID, not the CSF type as its ID.
The app writes index 0 for a temporary start. The inspected settings bit 0
means automatically starting the timer; it does not prove that confirmation
on the cooktop can be skipped automatically.

There is also a specific conversion discrepancy: the favorites save helper
`toCsfParameter` (`0x1012d1ff8`) writes the catalogue-derived
`ProgramTimer.defaultSeconds` directly to `csfTimerDuration`. The start path
does convert seconds to milliseconds. This was checked through the
ProgramTimer factory and its `toSeconds` calls.

It is unknown whether the firmware normalizes this during saving or reading,
or whether it is an app bug. Copying a `GetSavedCsf` result unchanged into
`StartOrModifyCsf` is therefore not yet a proven workflow. Descriptor limits
alone do not resolve this: two differently scaled values can both fall
within an advertised range.

The next step is a targeted comparison of a known saved program, its displayed
duration and its reported parameters. [READONLY-PROBE.md](READONLY-PROBE.md)
describes the tool prepared for that purpose. No program ID, timer unit or
unbridge command has been guessed.

A new, separate route uses four specific records from the public catalogue.
Those records and the app code establish exact default starts without reusing
a saved CSF message. Their initial zero timer value is proven through the
complete mapper and start sequence. These four starts are therefore now
prepared locally; see [ASSIST-PRESETS.md](ASSIST-PRESETS.md). This does not
resolve the uncertainty about saved Assists or ordinary timer setters.

## Additional investigation of saving

The Favorites editor builds one `SaveCsf` list containing up to three parameter
sets reconstructed from the catalogue for slots 3, 4 and 5. Null selections
are removed from that list. Slots 1 and 2 and old, unknown parameters are not
sent back by this app path. After the request, the app triggers `GetSavedCsf`,
but the editor does not compare complete parameters: it keeps only the
program IDs for slots 3–5 and waits 500 milliseconds.

For the four catalogue records without a timer, seconds and milliseconds
produce the same zero value. Their parameter construction for saving is now
known. Another question remains: does the firmware preserve, clear or reset
an omitted slot, and do slots 1–2 remain unchanged? A later authorized
comparison must record the complete lists before and after a deliberate
change in the app. Saving controls remain unavailable until then; neither
an individual slot change nor a clear command is guessed.
