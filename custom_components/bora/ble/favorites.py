"""Describe reported app-favorite slots without I/O or parameter conversion.

The app presents slots 3, 4 and 5. SaveCsf omission/preservation semantics
remain unverified; nothing in this module prepares a save or a start.
Catalogue labels identify an ID/type pair, not validated control parameters.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Final

from .presets import CATALOG, FRYING_CSF_TYPE, UINT32_MAX, X_PURE_PRODUCT

FAVORITE_SLOTS: Final = (3, 4, 5)
_CATALOG_LABELS: Final = {preset.preset_id: preset.name for preset in CATALOG}


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def supports_favorites(information: Mapping, descriptor: Mapping) -> bool:
    """Whether product and advertised index bounds support this presentation.

    This is a metadata check, not proof that GetSavedCsf or any write succeeds.
    Other CSF types remain displayable; FRYING support is not required to read
    an unknown favorite's raw parameters.
    """
    if not isinstance(information, Mapping) or not isinstance(descriptor, Mapping):
        return False
    product = information.get("product")
    if not _is_integer(product) or product != X_PURE_PRODUCT:
        return False
    csf = descriptor.get("csf_descriptor")
    if not isinstance(csf, Mapping):
        return False
    bounds = csf.get("index_range")
    if not isinstance(bounds, Mapping):
        return False
    minimum, maximum = bounds.get("min"), bounds.get("max")
    return (
        _is_integer(minimum)
        and _is_integer(maximum)
        and 0 <= minimum <= FAVORITE_SLOTS[0]
        and FAVORITE_SLOTS[-1] <= maximum <= UINT32_MAX
    )


def describe_favorites(parameters: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Describe all three slots from a successfully decoded SavedCsfResponse.

    Each slot has state, label, parameters and candidates. A unique record has
    deep-copied parameters; duplicate indices have no chosen parameters and
    retain every candidate. A known ID with a different/unknown CSF type keeps
    an unknown_<id> label. Targets, timers, presence and extra fields are copied
    unchanged. Invalid/missing IDs use "unknown" without fabricating an ID.

    Records outside app slots 3–5, or without a valid integer slot, are ignored.
    Callers must distinguish an unavailable read from a successful empty list.
    """
    records: dict[int, list[dict[str, Any]]] = {slot: [] for slot in FAVORITE_SLOTS}
    for parameter in parameters:
        if not isinstance(parameter, Mapping):
            continue
        slot = parameter.get("csf_index")
        if _is_integer(slot) and slot in records:
            records[slot].append(deepcopy(dict(parameter)))

    result = {}
    for slot, candidates in records.items():
        if not candidates:
            result[slot] = {
                "state": "empty", "label": "empty", "parameters": None, "candidates": []
            }
            continue
        if len(candidates) > 1:
            result[slot] = {
                "state": "ambiguous", "label": "ambiguous",
                "parameters": None, "candidates": candidates,
            }
            continue
        parameter = candidates[0]
        preset_id = parameter.get("csf_id")
        csf_type = parameter.get("csf_type")
        name = (
            _CATALOG_LABELS.get(preset_id)
            if _is_integer(preset_id) and _is_integer(csf_type) and csf_type == FRYING_CSF_TYPE
            else None
        )
        label = name if name is not None else (
            f"unknown_{preset_id}" if _is_integer(preset_id) else "unknown"
        )
        result[slot] = {
            "state": "known" if name is not None else "unknown",
            "label": label,
            "parameters": parameter,
            "candidates": [],
        }
    return result
