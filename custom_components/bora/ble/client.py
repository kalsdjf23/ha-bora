"""Appliance state and command validation above the BRPC transport."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime

from . import cooktop, diagnostic_client, extractor, favorites, identify, presets, zone
from .confirmation import command_confirmed
from .transport import BoraError, BrpcConnection, ConnectionLost, RpcError
from .wire import Message, ProtocolError, Stream

UNIMPLEMENTED = 12
UNAVAILABLE = 14
SIMPLE_FUNCTION_FIELDS = (
    "cleaning_lock_disabled",
    "pause_disabled",
    "warming_disabled",
    "timer_disabled",
    "hot_key_disabled",
)
CONTROL_PATHS = {
    *(
        f"/bora.generic.extractor.v1.ExtractorService/{method}"
        for method in (
            "SetExtractorMode",
            "SetDurationAfterRun",
            "StopAfterRun",
            "SetEggTimer",
            "SetEggTimerState",
        )
    ),
    *(
        f"/bora.generic.cooktop.v1.CooktopService/{method}"
        for method in ("SetPaused", "SetChildLock", "SetSignalVolume", "SetSpecificCooktopSetting")
    ),
    *(
        zone.SERVICE_PATH + method
        for method in ("SetMode", "SetTimer", "SetTimerState", "StopCsf", "StartOrModifyCsf")
    ),
}


class UnsupportedValue(BoraError):
    """The current appliance does not advertise the requested value."""


class CommandNotConfirmed(BoraError):
    """The readback is valid, but does not yet show the requested state."""


class BoraDevice:
    """Keep complete decoded snapshots; do not guess delta or off semantics."""

    def __init__(
        self, connection: BrpcConnection, updated: Callable[[], None] | None = None,
        *, favorites_updated: Callable[[], None] | None = None,
    ):
        self.connection = connection
        self._updated = updated
        self._favorites_updated = favorites_updated
        self.information: dict = {}
        self.descriptor: dict = {}
        self.diagnostic_snapshot: dict = {}
        self._state: dict = {"extractor": None, "cooktop": None, "zones": {}}
        self._ready = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._unsupported_streams: set[str] = set()
        self._assist_busy: set[str] = set()
        self._assist_uncertain: dict[str, tuple[str, bytes]] = {}
        self._favorites: dict | None = None
        self._favorites_epoch = 0

    @property
    def snapshot(self) -> dict:
        return deepcopy(self._state)

    @property
    def favorites_snapshot(self) -> dict | None:
        """The last explicitly read favorite bank from this connection only."""
        if self._closed or not self.connection.connected:
            return None
        return deepcopy(self._favorites)

    def invalidate_favorites(self) -> None:
        self._favorites = None
        self.diagnostic_snapshot.pop("saved_csf", None)
        self._favorites_epoch += 1
        if self._favorites_updated:
            self._favorites_updated()

    def _store_favorites(self, parameters: list[dict], epoch: int) -> None:
        self._assert_connected()
        if epoch != self._favorites_epoch:
            raise ConnectionLost("The saved-Assist read belongs to an earlier connection")
        self._favorites = {
            "slots": favorites.describe_favorites(parameters),
            "read_at": datetime.now(UTC).isoformat(),
        }
        # The diagnostic copy is updated and invalidated with the display
        # snapshot; it never outlives that snapshot as a separate live cache.
        self.diagnostic_snapshot["saved_csf"] = {"status": "ok", "data": deepcopy(parameters)}
        if self._favorites_updated:
            self._favorites_updated()

    @property
    def zone_uids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value for value in (self.descriptor.get("zone_uids") or {}).values() if value
            )
        )

    async def _query(self, command: tuple[str, bytes]) -> bytes:
        return await self.connection.rpc(*command)

    def _stream_callback(self, category: str, decoder):
        def update(body: bytes) -> None:
            status = decoder(body)
            if category == "zones":
                uid = status.get("uid")
                if uid not in self.zone_uids:
                    raise ProtocolError("Zone stream contains an unadvertised zone")
                self._state["zones"][uid] = status
            else:
                self._state[category] = status
            self._resolve_assist_starts()
            if self._ready and self._updated:
                self._updated()

        return update

    async def initialize(self, *, pair: bool = False, subscribe: bool = True) -> dict:
        """Read capabilities, subscribe, then obtain explicit initial snapshots."""
        async with self._lock:
            self._assert_open()
            return await self._initialize(pair=pair, subscribe=subscribe)

    async def _initialize(self, *, pair: bool = False, subscribe: bool = True) -> dict:
        self._ready = False
        self.invalidate_favorites()
        # Rebuilding subscriptions needs a fresh generation: an older stream
        # for the same path must not be mistaken for the new setup response.
        if self.connection.connected:
            await self.connection.disconnect()
        candidates = (
            (extractor.STREAM_PATH, "extractor", extractor.decode_status),
            (cooktop.STREAM_PATH, "cooktop", cooktop.decode_status),
            (zone.STREAM_PATH, "zones", zone.decode_status),
        )
        # An unsupported stream closes the attempted transport subscription.
        # Restart reads with that one stream omitted; never replay controls.
        for _attempt in range(len(candidates) + 1):
            try:
                self._assert_open()
                await self.connection.connect(pair=pair)
                self.descriptor = identify.decode_descriptor(
                    await self._query(identify.get_descriptor())
                )
                if not self.descriptor.get("extractor_descriptor"):
                    raise ProtocolError("Missing BORA extractor descriptor")
                try:
                    self.information = identify.decode_information(
                        await self._query(identify.get_information())
                    )
                except RpcError as err:
                    if (
                        err.code != UNIMPLEMENTED
                        or err.path != identify.get_information()[0]
                        or err.request_id is None
                        or err.stream != Stream.NONE
                    ):
                        raise
                    self.information = {}
                if subscribe:
                    for path, category, decoder in candidates:
                        if path in self._unsupported_streams or (
                            category == "zones" and not self.zone_uids
                        ):
                            continue
                        try:
                            await self.connection.subscribe(
                                path, self._stream_callback(category, decoder)
                            )
                        except RpcError as err:
                            # An established stream can fail another pending
                            # subscription. Only this path's setup response
                            # establishes that the attempted method is absent.
                            if (
                                err.code != UNIMPLEMENTED
                                or err.path != path
                                or err.request_id is None
                                or err.stream not in (Stream.NONE, Stream.START)
                            ):
                                raise
                            self._unsupported_streams.add(path)
                            break
                    else:
                        await self._read_statuses()
                        self._ready = True
                        return self.snapshot
                    continue
                await self._read_statuses()
                self._ready = True
                return self.snapshot
            except BaseException:
                await self.connection.disconnect()
                raise
        raise ConnectionLost("Unable to initialize BORA status subscriptions")

    async def _read_statuses(self) -> None:
        def store_extractor(body: bytes) -> None:
            self._state["extractor"] = extractor.decode_status(body)

        def store_cooktop(body: bytes) -> None:
            self._state["cooktop"] = cooktop.decode_status(body)

        await self.connection.rpc(*extractor.get_status(), received=store_extractor)
        await self.connection.rpc(*cooktop.get_status(), received=store_cooktop)
        self._state["zones"] = {
            uid: status for uid, status in self._state["zones"].items() if uid in self.zone_uids
        }
        for uid in self.zone_uids:
            unavailable_received = False

            def store_zone(body: bytes, expected_uid: str = uid) -> None:
                status = zone.decode_status(body)
                if status.get("uid") != expected_uid:
                    raise ProtocolError("Zone status does not match the requested zone")
                self._state["zones"][expected_uid] = status

            def failed_zone(error: RpcError, expected_uid: str = uid) -> None:
                nonlocal unavailable_received
                if error.code == UNAVAILABLE:
                    unavailable_received = True
                    # Apply in wire order: a later stream can restore the zone
                    # before this awaiting coroutine resumes.
                    self._state["zones"].pop(expected_uid, None)

            try:
                await self.connection.rpc(
                    *zone.get_status(uid), received=store_zone, failed=failed_zone
                )
            except RpcError as err:
                if err.code != UNAVAILABLE or not unavailable_received:
                    raise
                # An unavailable zone is unknown, not off. Keep reading the
                # other zones while the extractor can still report after-run.
        # A disconnect can arrive after the final reply but before its waiter
        # resumes. Do not overwrite that connection loss with a successful poll.
        self._assert_connected()
        self._resolve_assist_starts()

    def assist_start_blocked(self, uid: str) -> bool:
        """An ongoing or unobserved start cannot become another queued start."""
        return uid in self._assist_busy or uid in self._assist_uncertain

    def _resolve_assist_starts(self) -> None:
        # An idle readback cannot disprove delayed application. Keep uncertain
        # writes across reconnects until the corresponding program is observed.
        for uid, command in tuple(self._assist_uncertain.items()):
            if command_confirmed(command, self._state):
                del self._assist_uncertain[uid]

    async def refresh(self) -> dict:
        async with self._lock:
            self._assert_open()
            if not self.connection.connected:
                return await self._initialize()
            await self._read_statuses()
            return self.snapshot

    def _power_levels(self, kind: str) -> set[int]:
        return {item["index"] for item in (self.descriptor.get(kind) or {}).get("power_levels", [])}

    def validate_command(self, command: tuple[str, bytes]) -> None:
        """Validate data-driven limits again at the I/O boundary."""
        path, body = command
        if path not in CONTROL_PATHS:
            raise UnsupportedValue("This operation is not exposed by the integration")
        message = Message(body)
        if path == extractor.GET_PATH or path == cooktop.GET_PATH:
            raise UnsupportedValue("Status reads are not control actions")
        if path.endswith("ExtractorService/SetExtractorMode"):
            mode = message.message(1)
            which = mode.oneof({1, 2})
            descriptor = self.descriptor.get("extractor_descriptor") or {}
            if which == 2 and (
                2 not in descriptor.get("extractor_mode_types", [])
                or mode.int32(2) not in self._power_levels("extractor_descriptor")
            ):
                raise UnsupportedValue("Unsupported extractor level")
            if which == 1 and 1 not in descriptor.get("extractor_mode_types", []):
                raise UnsupportedValue("Automatic extraction is not supported")
            if which is None:
                raise UnsupportedValue("An extractor mode is required")
        elif path.endswith("ExtractorService/SetDurationAfterRun"):
            pure = (self.descriptor.get("extractor_descriptor") or {}).get("pure") or {}
            if message.uint(1) not in pure.get("after_run_durations", []):
                raise UnsupportedValue("Unsupported after-run duration")
        elif path.endswith("CooktopService/SetSignalVolume"):
            allowed = {item["index"] for item in self.descriptor.get("signal_volume_levels", [])}
            if message.int32(1) not in allowed:
                raise UnsupportedValue("Unsupported signal volume")
        elif path.endswith("CooktopService/SetSpecificCooktopSetting"):
            settings = (self._state.get("cooktop") or {}).get("cooktop_settings") or {}
            if settings.get("pure") is None:
                raise UnsupportedValue("Pure cooktop settings are unavailable")
            pure = message.message(1)
            which = pure.oneof(set(range(1, 9)))
            if which not in {1, 2, 3, 5, 6, 7}:
                raise UnsupportedValue("This Pure setting needs further validation")
            if which == 7:
                group = pure.message(7).message(1)
                if not all(group.has(i) and group.uint(i) in {0, 1} for i in range(1, 6)):
                    raise UnsupportedValue("All simple-mode function settings are required")
        elif path.startswith(zone.SERVICE_PATH):
            if path.endswith("/SetBridged"):
                uids = (message.text(1), message.text(2))
            elif path.endswith("/StartOrModifyCsf"):
                uids = (message.text(2),)
            else:
                uids = (message.text(1),)
            if not all(uid in self.zone_uids for uid in uids):
                raise UnsupportedValue("Unknown cooking zone")
            if not all(
                (self._state["zones"].get(uid) or {}).get("settings_present") is True
                for uid in uids
            ):
                raise UnsupportedValue("Current cooking zone status is unavailable")
            if path.endswith("/SetMode"):
                mode = message.message(2)
                which = mode.oneof({1, 2, 3})
                descriptor = self.descriptor.get("zone_descriptor") or {}
                supported = descriptor.get("zone_mode_types", [])
                if which == 1:
                    if 1 not in supported or mode.int32(1) not in self._power_levels(
                        "zone_descriptor"
                    ):
                        raise UnsupportedValue("Unsupported cooking level")
                elif which == 3:
                    pure = mode.message(3)
                    if pure.oneof({1, 2}) == 1:
                        if 3 not in supported or pure.message(1).int32(1) not in {1, 2, 3}:
                            raise UnsupportedValue("Unsupported warming mode")
                        # The fixed KEEP_WARM case is not established by the
                        # mode enum alone when variable support is absent.
                        if not descriptor.get("variable_heat_retention_support"):
                            raise UnsupportedValue("Heat retention support is not validated")
                    elif pure.oneof({1, 2}) == 2:
                        if 4 not in supported or pure.message(2).int32(1) not in self._power_levels(
                            "zone_descriptor"
                        ):
                            raise UnsupportedValue("Unsupported automatic heat-up level")
                    else:
                        raise UnsupportedValue("Unknown Pure zone mode")
                else:
                    raise UnsupportedValue("This zone mode requires a validated cooking workflow")
            elif path.endswith("/SetTimer"):
                self._validate_timer(
                    message.uint(2), self.descriptor.get("zone_descriptor"), "timer_limits"
                )
            elif path.endswith("/StartOrModifyCsf"):
                self._validate_assist_start(command)
        if path.endswith("ExtractorService/SetEggTimer"):
            self._validate_timer(
                message.uint(1), self.descriptor.get("extractor_descriptor"), "egg_timer_limits"
            )

    @staticmethod
    def _validate_timer(value: int, descriptor: dict | None, key: str) -> None:
        limits = (descriptor or {}).get(key)
        if not limits or not limits["min_duration"] <= value <= limits["max_duration"]:
            raise UnsupportedValue("Timer duration is outside the advertised limits")

    def _validate_assist_start(self, command: tuple[str, bytes]) -> None:
        """Only the four exact catalogued starts, on a known idle single zone."""
        message = Message(command[1])
        uid = message.text(2)
        parameters = zone.decode_csf_parameter(message.bytes(1))
        try:
            expected = presets.prepare_preset(
                self.information, self.descriptor, uid, parameters["csf_id"], 0
            )
        except presets.PresetError as err:
            raise UnsupportedValue(str(err)) from err
        if command != expected:
            raise UnsupportedValue("Only the exact catalogue default start is exposed")
        settings = (self._state.get("cooktop") or {}).get("cooktop_settings") or {}
        status = self._state["zones"].get(uid) or {}
        if (
            settings.get("pure") is None
            or status.get("settings_present") is not True
            or status.get("mode") != "power_level"
            or status.get("power_level") != 0
            or status.get("bridged") is not False
            or status.get("bridged_to_uid")
        ):
            raise UnsupportedValue("Assist start requires an idle, unbridged Pure cooking zone")

    async def execute(self, command: tuple[str, bytes]) -> dict:
        """Issue one command, then confirm state via reads; never optimistic."""
        if command[0] == zone.SERVICE_PATH + "StartOrModifyCsf":
            self._assert_connected()
            uid = Message(command[1]).text(2)
            if self.assist_start_blocked(uid):
                raise UnsupportedValue("An Assist start is already pending or unconfirmed")
            # Reserve before awaiting the lock, including the generic route.
            self._assist_busy.add(uid)
            try:
                async with self._lock:
                    return await self._execute_locked(command)
            finally:
                self._assist_busy.discard(uid)
                if self._ready and self._updated:
                    self._updated()
        async with self._lock:
            return await self._execute_locked(command)

    async def _execute_locked(self, command: tuple[str, bytes]) -> dict:
        self._assert_connected()
        self.validate_command(command)
        if command[0] == zone.SERVICE_PATH + "StartOrModifyCsf":
            # A local selection is not a queued operation. Check a fresh status
            # under the same lock before starting; never modify an active zone.
            await self._read_statuses()
            if self._ready and self._updated:
                self._updated()
            self.validate_command(command)
            # A cancelled RPC or missing acknowledgement can still have been
            # applied. Clear only after observing this particular program.
            self._assist_uncertain[Message(command[1]).text(2)] = command
        await self._query(command)
        await self._read_statuses()
        if not command_confirmed(command, self._state):
            raise CommandNotConfirmed("The requested state was not observed after the command")
        return self.snapshot

    async def start_assist(self, uid: str, preset_id: int) -> dict:
        """One explicit catalogue start; never advance physical confirmation."""
        self._assert_connected()
        try:
            command = presets.prepare_preset(
                self.information, self.descriptor, uid, preset_id, 0
            )
        except presets.PresetError as err:
            raise UnsupportedValue(str(err)) from err
        return await self.execute(command)

    async def set_simple_function(self, field: str, enabled: bool) -> dict:
        """Merge the complete group under the same lock as its write/readback."""
        async with self._lock:
            self._assert_connected()
            if field not in SIMPLE_FUNCTION_FIELDS or not isinstance(enabled, bool):
                raise UnsupportedValue("Unknown simple-mode function or invalid state")
            settings = (self._state.get("cooktop") or {}).get("cooktop_settings") or {}
            simple = (settings.get("pure") or {}).get("super_simple_mode") or {}
            current = simple.get("disabled_functions") or {}
            if not all(isinstance(current.get(key), bool) for key in SIMPLE_FUNCTION_FIELDS):
                raise UnsupportedValue("A complete simple-mode snapshot is required")
            values = {key: current[key] for key in SIMPLE_FUNCTION_FIELDS}
            values[field] = not enabled
            return await self._execute_locked(cooktop.set_super_simple_disabled_functions(**values))

    async def collect_diagnostics(self) -> dict:
        """Collect optional reads only on an already connected appliance."""
        async with self._lock:
            self._assert_connected()
            self.invalidate_favorites()
            epoch = self._favorites_epoch
            self.diagnostic_snapshot = await diagnostic_client.async_collect(self.connection)
            saved = self.diagnostic_snapshot.get("saved_csf", {})
            if (
                saved.get("status") == "ok"
                and favorites.supports_favorites(self.information, self.descriptor)
            ):
                try:
                    self._store_favorites(saved["data"], epoch)
                except ConnectionLost:
                    self.diagnostic_snapshot.pop("saved_csf", None)
                    raise
            return deepcopy(self.diagnostic_snapshot)

    async def refresh_favorites(self) -> dict:
        """One explicit read, without reconnect, polling, saving or starting."""
        async with self._lock:
            self._assert_connected()
            if not favorites.supports_favorites(self.information, self.descriptor):
                raise UnsupportedValue("Saved Assists are not established for this device")
            self.invalidate_favorites()
            epoch = self._favorites_epoch
            parameters = identify.decode_saved_csf(await self._query(identify.get_saved_csf()))
            self._store_favorites(parameters, epoch)
            return self.favorites_snapshot

    def _assert_connected(self) -> None:
        self._assert_open()
        if not self.connection.connected:
            raise ConnectionLost("BORA is unavailable; commands are not queued")

    async def close(self) -> None:
        self._ready = False
        self.invalidate_favorites()
        await self.connection.disconnect()

    def _assert_open(self) -> None:
        if self._closed:
            raise ConnectionLost("BORA client has been shut down")

    async def shutdown(self) -> None:
        """Invalidate queued work permanently before closing the connection."""
        self._closed = True
        await self.close()
