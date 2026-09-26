# Four prepared X PURE Assist programs

The integration now includes a fixed selection of four programs from the
[public BORA catalogue](https://boraone-backend.k8s-prd.cloud.bora.com/v1/automatic-programs?pimProductId=61596&page=1&pageSize=20).
That read request returned HTTP 200 on 25 September 2026 without an account,
cookies or an authentication header. It was a catalogue request, not an
appliance control operation. The integration uses the captured metadata
locally and makes no catalogue or account requests itself.

| Program | Catalogue ID | Default target |
| --- | --- | --- |
| Cook egg dishes | 62176 | 135 °C |
| Fry potato dishes | 62954 | 205 °C |
| Fry pancakes | 63120 | 180 °C |
| Fry breaded foods | 63121 | 170 °C |

These values are program settings, not measured pan temperatures. All four
use FRYING. Their catalogue limits are 120–220 °C; the first two have a step
value of 15 and the last two 10. The integration does not copy recipe
instructions or images. The necessary facts are recorded in a
[sanitized fixture](../tests/fixtures/x_pure_catalogue_2026_09_25.json).

## Prepared controls in Home Assistant

These controls have only been tested in simulation. The first physical test
with the HA adapter and cooktop has yet to take place.

1. Enable both general controls and cooking controls in the integration options.
2. Choose an **Assist to start** for the desired zone. This selection remains
   local; choosing it sends no appliance command. There is no default selection,
   and reloading the integration clears the selection.
3. Explicitly press **Start Assist**. The zone must have a known off state and
   be unbridged. The client reads this again before sending the command.
4. Complete the physical Assist confirmation on the cooktop. The integration
   does not skip this step or advance a reported confirmation phase itself.

This start button does not modify an existing active zone or cooking function.
The ordinary program status continues to show the phase actually received.
The existing button to stop a cooking program remains available separately.
These presets do not add an automatic stop after a chosen duration; the HA
start uses the default values from the identified app path.

The **Cooking program phase** and **Assist confirmation required** sensors
follow the reported appliance status. The first also shows `inactive` when
a known other zone mode is active. An unknown phase does not falsely report
that confirmation is no longer required. **Assist target temperature** is
only the reported setting of a recognizable program, not a measured pan
temperature. Making a different local selection does not change these
sensors. No temperature is displayed without a recognizable program and
a valid target value.

## Evidence for the exceptional values

The app retrieves these records with a fixed product filter of `61596` and
uses the numeric catalogue ID directly as `csfId`. For a new start, the
production caller writes `csfIndex=0`, even though the appliance descriptor
lists an index range of 1–5. The start code follows this established app value
instead of changing it to a saved-program slot.

These four records have no separate timer step or slider configuration.
Missing hour/minute/second fields become null and then zero seconds. The
mapper hides the timer screen; the start VM also begins with zero seconds
and writes it through its millisecond conversion as `csfTimerDuration=0`.
This is a specific app-start exception for these four records, not a general
meaning of a zero timer value. It does not rename or change the raw CSF timer
limits of 10,000–7,250,000 in the recording.

`csfSettings=0` follows from the production conversion `!cooktopTimer`, with
`cooktopTimer=true` in all four records. The other catalogue flag,
`userTimerstart`, is a separate field and is not the source of this bit value.
With one selected zone, the start caller retains FRYING; it changes this to
GRILL only when two zones are selected. This preparation offers only a single
zone, without a bridge or unbridge command.

The recorded X PURE reports FRYING for all four zones, target limits of
120–240 and step limits of 1–120. The code rechecks the selected zone, product
type and complete recipe limits. It does not impose an invented step grid:
the actual catalogue value 205 does not fit `120 + n × 15`.

## Implementation limits

The runtime accepts only the exact default start for these four records,
on X PURE product type 2 with matching capabilities. A different temperature,
duration, index, bit value, recipe ID or program variant is rejected. The
presence of a low-level encoder does not provide a generic HA start service.

Statuses are read before and after the single write. Only a matching CSF
message in phase preheat, confirmation-required or active confirms that the
program is being reported. This does not prove that a temperature has been
reached, physical confirmation has been completed or cooking has finished.
Missing or differing readback produces a notification; the command is not
repeated. Reconnection also does not send a start from the local selection.

A zone is reserved for this start before waiting for other Bluetooth
operations. A concurrent second start is rejected rather than queued for
later. From the moment of transmission, an uncertain start also remains
blocked after an error, cancellation or reconnection. Only a later CSF status
with the corresponding parameters and phase preheat, confirmation-required
or active resolves that uncertainty; the ordinary guard against modifying
an active program still applies.

A reported off state does not prove that a delayed start can never be
applied. It therefore does not clear the block. If the first command was
never applied, the zone may remain blocked from new Assist starts for the
lifetime of this client instance. This guard does not persist across an
integration reload or HA restart; reloading does not confirm the appliance's
state. Always check the cooktop after an uncertain start before considering
another start.

Saved Assists, custom parameters, other CSF types, modification during an
active program and the bridge workflow remain separate research topics.
The save/start discrepancy in [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md) is avoided
here by using specific catalogue data, not by resending saved parameters.
None of these four starts was executed on the actual cooktop during this
preparation.
