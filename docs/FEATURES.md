# Features and conditions

This list describes the locally implemented integration. A codec, entity, or
successful simulation test does not prove that a real cooktop accepts the
corresponding command. Current physical evidence is in
[VALIDATION.md](VALIDATION.md).

## General conditions

- **Monitoring:** no control option is required, but a connection and relevant
  status must be available.
- **General control:** the `enable_controls` option must be enabled.
- **Cooking control:** both `enable_controls` and `enable_cooking_controls`
  must be enabled.
- Power levels, zone names, and available capabilities are read from the
  appliance descriptor. Settings in a `pure` message are offered only when
  that extension is present in status.
- Not every setting has a dedicated capability flag. For those settings, the
  known message schema is the basis; physical support still needs confirmation.
  An appliance can reject a method with `UNIMPLEMENTED`.
- Missing or unknown values remain unknown. A disconnected connection makes
  entities unavailable; an inactive status subscription does not mean power or
  remaining time is zero.
- An individual zone-status query with code 14 (`UNAVAILABLE`) makes only that
  zone unknown; the fan and other valid status remain usable. Zone control
  requires current zone status. See [the cooking
  observation](COOKING-OBSERVATION.md).

## Fan

The latest stop-only trial returned code 12 directly from `SetExtractorMode`
requesting manual level 0. The user had manually set the fan to 1, and two
separate status rounds after the failed command still showed fan 1 and all
zones 0. Manual shutdown confirmation remains pending in this record.

The older 0 → 1 → 0 trial also ended with code 12 in both control phases, but
its error origin remains unresolved. No successful control is proven; the
controls below are implementation preparation, not verified appliance
functionality. This does not establish that every write is unsupported.
See [the hardware report](HARDWARE-CHECKS.md). Reading levels did succeed.

| Entity or feature | Conditions and behaviour |
| --- | --- |
| Power and mode | Monitoring; level with label from the descriptor. |
| Fan: manual levels | General control; advertised levels and manual mode only. Percentage distributes across ordinary levels without claiming a physical airflow rate. |
| Fan: automatic and boost | General control; automatic only when an automatic mode is advertised. A special power label such as `P` becomes a separate preset. |
| Remaining after-run and after-run active | Monitoring; observed milliseconds are converted to seconds. |
| Configured after-run time | Monitoring; the known enum label is shown in minutes. |
| Select after-run time | General control; requires `pure` status and a list of supported after-run values. |
| Stop after-run | General control; available only when remaining after-run time is positive. |

On the researched appliance, fan levels `0` through `8` are ordinary levels,
and index `9` has label `P`. At 100%, the fan selects the highest ordinary
level; boost requires the explicit preset. These are appliance-descriptor
values, not a fixed assumption for every model.

The captured after-run configuration is 30 minutes, whereas the descriptor
offers 10, 15, and 20 minutes for changes. The separate status sensor can
therefore show 30 minutes without adding that value as a selectable option.

## Cooking zones

| Entity or feature | Conditions and behaviour |
| --- | --- |
| Power and mode | Monitoring per advertised zone; label, timer data, and any bridged zone are attributes. |
| Timer duration, remaining time, and timer active | Monitoring without control options; duration and remaining time are shown as seconds from supported milliseconds, while retaining raw attributes. A missing timer message makes entities unavailable and their values unknown. |
| Residual heat | Monitoring of the reported flag; not a measured temperature. |
| Pan detection active | Diagnostic flag; does not prove a pan is present. |
| Bridge status | Monitoring of the bridge flag and bridged-zone identity. |
| Cooking program / CSF | Monitoring of type and raw parameters; recognised catalogue programs receive their name as an attribute. This comes from appliance status, not local selection. |
| Program phase and Assist confirmation required | Separate phase sensor and binary confirmation sensor. A known different zone mode gives `inactive`; unknown phases make the confirmation value unknown. |
| Assist target temperature | Received target value in °C for the four recognised FRYING programs on a suitable X PURE zone. This is not a measured pan temperature or a supplied catalogue default; unknown programs and invalid values remain unknown. |
| Set power | Cooking control and advertised power mode. Contiguous indexes get a numeric input; gaps in the list use a selection list. |
| Heat retention | Cooking control, `pure` status, advertised heat-retention mode, and variable heat-retention support. Choices are melt, keep warm, and simmer according to the known enums. |
| Automatic heat-up | Cooking control, `pure` status, and advertised automatic-heat-up mode. Choices use ordinary numeric power labels, without the boost label. |
| Stop cooking program | Cooking control and advertised CSF mode; available only when the zone reports CSF as its current mode. |
| Select and start Assist | Cooking control, X PURE product type 2, and suitable FRYING capabilities; four concrete catalogue programs. Selection is local; start requires a separate button and a freshly read off, unbridged zone. |

The researched X PURE has zone identities `front_left`, `back_left`,
`back_right`, and `front_right`. Ordinary zone power runs from `0` through `9`;
index `10` has label `P`. This differs from the fan boost index. Zone-timer
evidence comes from explicit conversions in app code, not a new physical timer
trial; see [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).

Fixed heat-retention control with `variableHeatRetentionSupport=false` is not
yet supported by evidence. Received heat-retention status remains readable;
control currently requires advertised variable support. The researched X PURE
does report it.

Assist starts follow the supported default parameters from an anonymously read
catalogue and the app code. The integration does not retrieve this data from
the internet and provides no timer or temperature of its own for these starts.
See [ASSIST-PRESETS.md](ASSIST-PRESETS.md) for the four programs, physical
confirmation, and the special index and timer value zero.

Saved app favourites additionally have three separate sensors for slots 3–5
and a **Refresh saved Assists** button. They use one explicit read query and
remain available with control disabled. Unknown programs and duplicate slot
numbers are shown recognisably; loss of connection or a failed read clears
previous values. The data neither start nor alter anything. See
[SAVED-ASSISTS.md](SAVED-ASSISTS.md) for snapshots, read date, and the
separate boundary around storage control.

## Cooktop and settings

| Entity or feature | Conditions and behaviour |
| --- | --- |
| Pause status, child-lock status | Monitoring. |
| Control pause and child lock | Cooking control; the child lock uses the known lock enums. |
| Cleaning-lock status, simple-mode status | Monitoring; requires `pure` status. |
| Cleaning lock, permanent child lock, automatic pan detection | Cooking control and `pure` status. |
| Signal volume | General control; descriptor labels and indexes only. |
| Touch sensitivity | General control and `pure` status; slow, standard, or fast according to the schema. |
| Maximum operating time | Cooking control and `pure` status; enum choices `default`, `high`, and `max`, without an unproven time unit. |
| Features in simple mode | Cooking control and present settings group. Separate switches for cleaning lock, pause, heat retention, timer, and quick key. This enables or disables a feature within simple mode, not simple mode itself. |
| Error codes | Diagnostic count, raw codes, and known SDK labels. No inferred cause or repair advice. |
| Connectivity, recovery status, ready for sleep | Diagnostics. `ready_for_sleep` is not a reliable physical on/off indicator. |
| Filter replacement needed | Binary monitoring for explicit recirculation. The supported app threshold is raw remaining value zero; an unknown type or exceptional value remains unknown. No hours or percentage. |

A change to a simple-mode feature is merged under the same appliance lock with
the other four fields from the latest status. This prevents two concurrent
changes from each sending an outdated complete group back. Every control
command is validated and followed by a status read. Only the observed relevant
value can confirm the command. A differing or missing value produces a notice
that the command is not yet confirmed, while available real status remains
visible. There is no retry; a later status stream can still report the change.
Stopping CSF is confirmed only when a known different zone mode is observed.
That alone does not prove that the zone is no longer heating; its power remains
visible separately. These comparisons were tested offline, not on hardware.

## Diagnostics

The normally disabled **Refresh diagnostics** button is available with both
control options disabled. When explicitly pressed, it requests optional Wi-Fi
status, heartbeat status and period, saved CSF data, and system and user events
once, with a requested and locally enforced limit of 20 records per event
list. The report retains wire order and includes `received_count` and
`omitted_count`. System and user events have separate SDK names alongside
their raw numeric types and timestamps; unknown types keep their raw values.
These are historical categories, not current faults. Timestamp units and
chronological ordering remain unverified. This is not periodic collection.

A method is marked unsupported only for an attributed code-12 response to
that query. A status-stream error interrupting another request is recorded
as an error with its original RPC context, without declaring the interrupted
method unsupported or exposing raw error text.

The **Last reported Wi-Fi status** diagnostic sensor is disabled by default.
Enable it and the **Refresh diagnostics** button in Home Assistant's entity
settings, then press the button to read the optional status. Both work with
control options disabled. No Wi-Fi query is sent by enabling the sensor,
normal status polling, reconnecting, or restoring the integration.

The sensor retains the named status, including distinct `wifi_connected`,
`no_internet` and `internet_access` values. Unknown enums remain
`unknown_<code>`. Its only extra attributes are `connection_status` (the raw
code) and `last_read` (the UTC time that the Wi-Fi response was decoded).
It exposes no SSID, MAC/IP address or time zone. This is the last explicitly
read result, not a continuously updated connection indicator.

The sensor is unavailable until a usable response arrives. A missing response
wrapper is not treated as an off or unspecified state. A new explicit refresh
clears the old value first; failed, unsupported or cancelled reads cannot leave
it displayed as current. Disconnect, reconnect, reinitialization and unload
also clear it. Late results from an invalidated collection cannot restore it.
These behaviors have offline and HA-service tests with simulated Bluetooth;
the optional method still needs a physical test on the target appliance.

Home Assistant’s diagnostics download exports only the already present cache;
downloading itself causes no BLE traffic. Known identifying and secret fields
are redacted. Review an export before sharing it publicly, especially for new
firmware or still-unknown fields.

## Intentionally not offered as controls yet

- **Timer control:** zone-timer status is now available in seconds. The units
  of individual setter fields, limits, and the cooking timer remain open.
  There is therefore no time input yet; see
  [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).
- **Filter lifetime:** the app alert is available under the conditions in
  [FILTER-EVIDENCE.md](FILTER-EVIDENCE.md). Raw status and descriptor metadata
  do not yet provide hours, percentage, replacement date, or reset meaning.
  The filter-type list does not prove which filter is installed.
- **Bridge on/off:** the codec for two zone identities is known; safe unbridge
  semantics and physical operation are not validated. No HA control is offered.
  The examined `bridgeSelectedAction` in the app leads through `SelectZones`
  to a local selection of two zones. That path alone does not prove a BLE
  command.
- **Other CSF starts and modification:** the four catalogue starts above are
  prepared; other types, custom parameters, active-program changes, and saved
  presets remain open. The save path writes seconds without conversion, while
  the start path converts to milliseconds. See
  [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md). Every start requires suitable
  per-zone capabilities; a global program label does not prove zone support.
- **LED, dealer, Wi-Fi provisioning, firmware, reset, and debug writes:** not
  offered. There is no general service for sending arbitrary RPCs.
- **Energy and operating hours:** no supported measurement method was found;
  heartbeat counters and event names are not presented as such sensors.

[APP-COVERAGE.md](APP-COVERAGE.md) compares this preparation with broader app
features. The tool in [READONLY-PROBE.md](READONLY-PROBE.md) completed a
physical 60-second read-only report workflow and can support a later agreed
read-only trial. Pairing, optional diagnostics, and interrupted connections in
that workflow have only undergone offline testing.
