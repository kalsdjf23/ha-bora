# Filter warning: what is and is not established

Additional static analysis on 26 September 2026 of BORA One 1.9.1,
build 130922. The app was not run and no new appliance connection was
made for this analysis.

## Evidence for the warning

The Pure status mapper reads `remainingFilterLifetime` and sets the boolean
`shouldChangeFilter` when the value is less than 1. The Swift view uses that
boolean to display the odor filter replacement warning. This follows the
data from the status field to the warning; it is not an interpretation of
an RPC name alone.

The decisive arm64 addresses are `0x1010dd85c–0x1010dd864` for reading and
comparing, `0x1010de434–0x1010de438` for storing the boolean, and
`0x10009b0f8–0x10009b108` for the Swift warning branch.

## Behavior in Home Assistant

The **Filter replacement required** binary sensor does not require controls
to be enabled. It uses only the latest received Pure settings:

- With explicit recirculation (`extraction_type=1`) and a remaining value
  of zero, the warning is on. Positive values up to and including
  `0x7fffffff` produce an off state.
- With extraction to the outside, an unknown type, missing dealer
  configuration or an out-of-range value, the warning remains unknown.
- Without Pure status or an available connection, the sensor is unavailable.

Restricting this to known recirculation is an integration design choice.
The inspected app comparison and local warning branch do not themselves
check the extraction type; an enclosing screen condition cannot be ruled
out. A zero value alone is therefore not used to recommend filter replacement
for extraction to the outside.

The protocol field is uint32, but the app compares a signed Int. The meaning
of values from `0x80000000` onward is unknown. They are not converted to a
negative lifetime or a replacement warning. An absent entire Pure message
is not treated as zero either; an absent scalar within a present Protobuf
message has its normal zero default according to that schema.

## Remaining questions

This evidence does not establish a unit for `remainingFilterLifetime` or
`FilterUnit.lifetime`. No remaining hours, percentages or predicted replacement
dates are calculated. A list of supported filter types does not establish
which filter is fitted. The meaning of filter reset remains unknown, and
no reset button has been added.

All earlier local protocol recordings were also checked for this. They contain
only two filter values: 7234 and 7230, received 150.002 seconds apart. The exact
active operating time and internal update frequency were not recorded. This
decrease therefore does not prove minutes, hours or any other time unit and
is not converted into remaining operating time.

The threshold, unknown values and HA availability have been tested offline.
The warning still needs comparison with the actual app and cooktop; the
appliance's filter was not reset during this preparation.
