# Local BORA protocol

This independent implementation was derived from the message definitions in
the locally inspected BORA One app and checked against selected recordings
from one X PURE (PUXU2R, BLE revision 3.0.9). The official app, its binary,
account information and raw private recordings are not part of this project.
A method's presence in the app does not prove that every appliance supports
it. Device descriptors constrain the values offered by the integration.

## BLE and pairing

The custom service is `64cbfe50-126b-17ac-774e-f6fa40487dac`.
The other characteristics share the same suffix:

| Characteristic | Purpose |
| --- | --- |
| FE51 | BRPC requests; writes with ATT acknowledgement |
| FE52 | Protected response channel; notifications |
| FE53 | Bonding state: 00 unpaired, 01 paired, 02 in progress |

The transport uses conservative chunks of no more than 20 bytes.
Home Assistant supplies the current BLE device through its Bluetooth manager;
no separate scanner is started. Initial pairing happens only after confirmation
in the configuration flow. A normal reconnect checks the existing bond and
may prompt for reauthentication.

Reads have succeeded from a paired Mac. Pairing through Linux or a Bluetooth
proxy still requires physical testing. macOS peripheral IDs are specific to
the host; they are not stored as universal MAC addresses.

## Framing and BRPC

A frame is `7E + escaped(payload + CRC32) + 7C`. CRC32 is big-endian;
the checksum is calculated over the Protobuf payload. Bytes 7C, 7D and 7E
are escaped as 7D5C, 7D5D and 7D5E, respectively. Notifications may contain
frame fragments or multiple frames. Invalid CRCs, invalid fields and frames
larger than 1 MiB are rejected.

| Request field | Number | Type |
| --- | --- | --- |
| path | 2 | string |
| id | 3 | uint32, unique and nonzero |
| body | 4 | bytes containing the specific Protobuf request |
| stream | 6 | NONE=0 or STOP=2 |

| Response field | Number | Type |
| --- | --- | --- |
| code | 2 | response code; 0 for success |
| request_id | 3 | uint32 |
| body | 4 | bytes containing the specific Protobuf response |
| error | 5 | error message; must not be treated as success |
| stream | 7 | NONE=0, CONTINUE=1, STOP=2, START=3 |

A stream starts with a normal request to `Stream…`. START acknowledges
the subscription; CONTINUE delivers updates. STOP uses the subscription's
original path and request ID. START does not guarantee an initial snapshot,
so explicit status reads follow subscription. Unary responses and stream
updates are processed in arrival order so that an older snapshot cannot
overwrite a newer update.

Request IDs are not reused while an associated request or subscription
exists. Notifications from an old connection are ignored. A control request
that times out may still have reached the appliance. The integration never
replays that command.

## Services and evidence

The library contains independently implemented codecs for the Identify,
Extractor, Cooktop and Zone services, plus optional diagnostic reads.
The overview in [FEATURES.md](FEATURES.md) distinguishes HA entities, codec
support and validation still needed. There is no HA service for arbitrary
RPCs. Firmware operations, factory resets, provisioning and dealer settings
are not exposed as controls.

The sanitized fixture `tests/fixtures/x_pure_3_0_9.json` contains 15 sessions
with 39 valid responses. It provides evidence for specific reads, framing
and extractor stream updates; it does not record successful control commands.
Encoder and entity tests provide offline evidence for the implementation.

A successful RPC acknowledges receipt, not that the requested value is
already active. The client reads status back and compares the relevant
fields. If the value is missing or differs, HA reports the command as still
unconfirmed and displays the status actually received. No further write is
issued. Later streams may show the change; their timing and the behavior of
physical controls still require testing on the appliance.

## Optional event history

System and user histories have separate `EventType` enums. Static analysis of
BORA One 1.9.1 established system values 0–99 and user values 0–16. The
namespace-specific decoders retain `event_type` and `timestamp` and add the
exact SDK `event_type_name`, or `unknown_<value>` for an unrecognized code.
The generic decoder remains numeric because it has no namespace context.

For example, system code 5 is `EVENT_TYPE_BLE_SERVER_STARTED`, while user code
5 is `EVENT_TYPE_EXTRACTOR_DATA_UPDATE`. System code 33 is
`EVENT_TYPE_WIFI_CONNECTED`. A recorded category does not establish the
appliance's current state or the cause of a fault. Timestamp units and list
ordering have not been established.

Explicit diagnostics request 20 entries per history and retain at most 20 in
wire order even if a peer returns more. Counts show the total received and
number omitted. The names and retention behavior are tested offline; optional
history reads still require physical validation on the target appliance.

## Semantics that are not inferred

- `remainingAfterRun` is proven to use milliseconds. The observed after-run
  setting is 30 minutes, while the descriptor advertises only 10, 15 and 20
  minutes as writable options. The reported setting and selectable options
  remain separate.
- Extraction uses index 9 for `P`; cooking zones use index 10 for `P`.
  Indices and labels are read from the descriptor.
- `readyForSleep=false` was also observed when the cooktop was physically
  switched off. This field is not a power state. `potDetectionActive` likewise
  does not prove that a pan is actually present.
- App conversions establish that zone status Timer.duration/remaining use
  milliseconds; they are displayed in seconds. The separate timer setter
  fields, egg timer and filter lifetime retain their earlier evidence limits;
  see [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).
- Super Simple Mode writes the complete group of five disabled functions.
  The integration changes this group under a lock, with confirmed readback
  between changes. This is not an on/off switch for the mode itself.
- Four CSF catalogue starts combine specific public records with the
  reconstructed production caller. Their fixed zero index and timer values
  are explicit app-start exceptions, not guesses based on descriptor ranges.
  See [ASSIST-PRESETS.md](ASSIST-PRESETS.md). No supported workflow has yet
  been established for other CSF controls or unbridging a zone.
- The inspected Swift app action `bridgeSelectedAction` calls `SelectZones`;
  that branch stores a pair of zone identities in the selection model and
  returns. This proves local selection, not a `SetBridged` command. The
  presence of generated service adapters does not prove app usage either.
