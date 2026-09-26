# Standby, Bluetooth availability, and waking the cooktop

Remote wake is **not implemented or verified**. The integration can refresh
status and reconnect when Bluetooth is reachable. That does not establish
that it can switch on the main appliance or restore an unavailable radio.
The absence of a wake method in the inspected app wrappers is not proof that
every firmware or transport makes remote wake impossible.

## Observed states

The initial supervised standby observation established two distinct cases:

| State | Evidence | Meaning for the integration |
| --- | --- | --- |
| Panel off, Bluetooth still reachable | Status reads and a new stream subscription worked after the user confirmed that the zones and extractor were off | Read and reconnect operations can work during this interval; this is not proof of main-appliance wake |
| Later Bluetooth-unreachable state | A connection timed out and a subsequent scan found other devices but no X PURE; manual panel-on then restored a bonded connection | Deep standby is a possible explanation, but the observation does not exclude range, another client, or radio behaviour |

The received `connectivitySetting` remained `ON` (4), while `readyForSleep`
was false even with the appliance physically off. Neither field is a proven
main-power indicator. The observation does not establish a fixed sleep timer
or continuous standby reachability. “Deep standby” here describes a working
hypothesis, not a separately verified firmware state.

## Repeated observation on 26 September 2026

A new supervised trial separated after-run from the fully stopped state.
The user corrected an initial all-off report because extraction was still
running, then confirmed stopping after-run with the panel off and the phone
app closed. That corrected confirmation was recorded by 07:37:58 UTC.
The preceding fan-level-1 readings must not be treated as confirmed silent
standby or evidence of a stale value.

The research client was disconnected throughout the discovery phase. Its
20-second discovery windows, separated by 10 seconds, last saw X PURE in
the window ending at 07:38:41 UTC. The next two windows, ending at 07:39:11
and 07:39:41 UTC, found no X PURE but did find 17 and 18 nearby devices.
The scanner then stopped. These samples establish a repeated loss of local
visibility after shutdown, not its exact instant, a fixed sleep delay, or a
particular firmware power state.

With the scanner stopped, the official BORA One app on the paired Mac was
initially visibly disconnected. One Connect attempt remained on
`connecting` / `Stay close to your BORA appliance` for approximately one
minute and produced no fresh status screen. The attempt was cancelled with
Disconnect; the app returned to `not connected`. No fan or heating action
was requested. This trial did not demonstrate an official-app wake path
on the Mac. It does not establish the result on an iPhone or exclude an
unexamined cloud transport.

## Official and static evidence

The [official X Pure manual, version 03](https://www.bora.com/product-documentation/operating-and-installation-instructions/umim-xpure-en.pdf)
documents a long press of the physical power button for switching on/off
(§5.3.1, printed p. 19). Pairing requires connectivity to be enabled and
confirmation at the appliance (§6.3, p. 24). The `Con` menu persistently
enables/disables connectivity (§8.1, p. 26); it does not promise that Bluetooth
advertising continues indefinitely while the panel is off or describe a
remote wake command.

Read-only inspection of BORA One 1.9.1, build 130922, found:

- No main-power, wake, or connectivity-setting setter among the 54 inspected
  `bora.generic` RPC wrappers. `RestartConnectivityModule` is a separate
  restart operation, not a demonstrated wake or connectivity toggle
  (wrapper `0x10091e7dc`).
- A `WakeUp` wrapper does exist at `0x100c321f0`, but belongs to
  `clean_sys.generic.control.v1.BaseControlService`. It sends the method
  string `WakeUp` through `BleService.fetch` at `0x100c32348`. This different
  namespace is not evidence of X PURE support and still requires a working
  transport.
- The `Heartbeat` wrapper at `0x100996f94` has an empty request/response.
  Neither its name nor the debug heartbeat controls establishes a wake or
  keep-awake mechanism. Earlier reads worked for several minutes without
  an application heartbeat.
- The event label `ENERGY_STANDBY_UART_WAKEUP` (enum initializer
  `0x1009b9708`) names a system event, not an executable BLE command.
- The English app resource keys
  `add_device_discovery_failed_device_off_subtitle` and
  `device_details_connection_error_device_not_found_description` direct
  users to ensure that the appliance is switched on and nearby; the latter
  also mentions another connected user. This supports treating an offline
  appliance as a connection prerequisite, not assuming an app wake path.

Addresses are unslid addresses in that inspected arm64 app build. These
findings do not cover unknown firmware methods or prove that the official
app cannot use another transport.

## Current implementation and next discriminating test

The HA coordinator schedules ordinary status reconciliation every 30 seconds.
When disconnected, the client reconnects, reads metadata, rebuilds supported
subscriptions, and reads fresh status. It never replays controls. These are
connection-recovery operations; they cannot deliver a GATT RPC without a
working Bluetooth connection. No heartbeat configuration, connectivity
restart, guessed wake command, or heating/extraction command is used to
keep the appliance awake.

The repeated observation above performed the discovery and official Mac-app
comparison with the panel left off. A remaining discriminator is the
official iPhone app with phone Bluetooth disabled and Wi-Fi left enabled,
without changing the appliance's network configuration. It must obtain
**fresh** status or independently corroborated wake to establish an
alternative transport; a cached app screen is insufficient. Compare any
success with ordinary Bluetooth availability and manual panel-on, using
one client at a time.

If the app succeeds, identify its transport and exact request before adding
a wake action. If it also requires panel-on, the currently supported recovery
remains manual activation followed by normal reconnect. A separate bounded
comparison of an open read-only connection versus no connection can test
whether ordinary polling prolongs availability; it would establish
keep-alive behaviour, not wake from an already unreachable state.
