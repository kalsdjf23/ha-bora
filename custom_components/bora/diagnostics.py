"""Export cached BORA diagnostics with recursive identifier redaction."""
from __future__ import annotations

import ipaddress
import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

REDACTED = "**REDACTED**"
_BINARY = "**REDACTED BINARY**"
_UNKNOWN = "<unsupported value>"
_MAX_DEPTH = 40
_SENSITIVE_NAMES = {
    "fd", "enr", "identifier", "identifiers", "cmidentifier",
    "partidentifier", "uniqueid", "deviceid", "entryid", "configentryid",
    "password", "credentials", "token", "accesskey",
}
_MAC = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")
_UUID = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![0-9a-f])")
_IP = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6 = re.compile(r"(?i)(?<![\w:])[0-9a-f]*:[0-9a-f:]+(?![\w:])")


def _sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    return (
        normalized in _SENSITIVE_NAMES
        or "serial" in normalized
        or "ssid" in normalized
        or "address" in normalized
        or normalized.endswith("identifier")
        or normalized.endswith("identifiers")
    )


def _collect_secrets(value: Any, secrets: set[str], *, sensitive: bool = False,
                     seen: set[int] | None = None, depth: int = 0) -> None:
    """Find identifier values so aliases and identifier-keyed maps redact too."""
    if depth > _MAX_DEPTH:
        return
    if isinstance(value, str):
        if sensitive and value:
            secrets.add(value)
        return
    if sensitive and isinstance(value, int) and not isinstance(value, bool):
        # Absent protobuf identifiers/IP addresses decode as zero. Redact the
        # sensitive field itself, without hiding unrelated zero-valued status.
        if value != 0:
            secrets.add(str(value))
        return
    if not isinstance(value, (Mapping, list, tuple, set, frozenset)):
        return
    if seen is None:
        seen = set()
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, Mapping):
        for key, item in value.items():
            if sensitive:
                _collect_secrets(key, secrets, sensitive=True, seen=seen, depth=depth + 1)
            _collect_secrets(item, secrets, sensitive=sensitive or _sensitive_key(key),
                             seen=seen, depth=depth + 1)
    else:
        for item in value:
            _collect_secrets(item, secrets, sensitive=sensitive, seen=seen, depth=depth + 1)
    seen.remove(id(value))


def _redact_text(value: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if value.casefold() == secret.casefold():
            return REDACTED
        # Short identifiers redact whole tokens in text; longer identifiers
        # also redact embedded aliases such as device-ID/entity suffixes.
        pattern = re.escape(secret)
        if len(secret) < 4:
            pattern = rf"(?<!\w){pattern}(?!\w)"
        value = re.sub(pattern, lambda _match: REDACTED, value, flags=re.IGNORECASE)
    value = _MAC.sub(REDACTED, value)
    value = _UUID.sub(REDACTED, value)

    def redact_ip(match: re.Match[str]) -> str:
        try:
            ipaddress.ip_address(match.group())
        except ValueError:
            return match.group()
        return REDACTED

    value = _IP.sub(redact_ip, value)
    return _IPV6.sub(redact_ip, value)


def _sanitize(value: Any, secrets: tuple[str, ...], *, seen: set[int] | None = None,
              depth: int = 0) -> Any:
    """Return a fresh JSON-safe structure without stringifying opaque objects."""
    if depth > _MAX_DEPTH:
        return "<depth limit>"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return _sanitize(value.value, secrets, seen=seen, depth=depth + 1)
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if isinstance(value, (bytes, bytearray, memoryview)):
        # Raw protobuf/backend data may encode identifiers. Hex is reversible.
        return _BINARY
    if isinstance(value, int):
        return REDACTED if str(value) in secrets else value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if not isinstance(value, (Mapping, list, tuple, set, frozenset)):
        return _UNKNOWN
    if seen is None:
        seen = set()
    if id(value) in seen:
        return "<recursive reference>"
    seen.add(id(value))
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if isinstance(key, str):
                safe_key = _redact_text(key, secrets)
            elif isinstance(key, (int, float, bool)) or key is None:
                safe_key = _redact_text(str(key), secrets)
            else:
                safe_key = f"redacted_key_{index}"
            if safe_key in result:
                # Preserve entries when multiple private map keys redact to the
                # same string; do not reintroduce the original key to disambiguate.
                safe_key = f"{safe_key}_{index}"
                while safe_key in result:
                    safe_key += "_"
            result[safe_key] = REDACTED if _sensitive_key(key) else _sanitize(
                item, secrets, seen=seen, depth=depth + 1
            )
    else:
        result = [_sanitize(item, secrets, seen=seen, depth=depth + 1) for item in value]
    seen.remove(id(value))
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Download existing snapshots only; this function never makes BLE reads."""
    coordinator = getattr(entry, "runtime_data", None)
    device = getattr(coordinator, "device", None)
    data = {
        name: getattr(device, name, None)
        for name in ("information", "descriptor", "snapshot", "diagnostic_snapshot")
    }
    secrets: set[str] = set()
    _collect_secrets(data, secrets)
    # Config is not exported, but its address/identifier can occur as a map key
    # or embedded in a cached backend message without a sensitive field name.
    _collect_secrets(getattr(entry, "data", {}), secrets)
    unique_id = getattr(entry, "unique_id", None)
    if isinstance(unique_id, str) and unique_id:
        secrets.add(unique_id)
    return _sanitize(data, tuple(sorted(secrets, key=lambda item: (-len(item), item.casefold()))))
