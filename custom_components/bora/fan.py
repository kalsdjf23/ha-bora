"""Extractor fan with device-defined levels and separate automatic/boost modes."""

from __future__ import annotations

import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.exceptions import HomeAssistantError

from .ble import extractor
from .entity import BoraEntity, descriptor, extractor_settings, levels, nested, option_labels


class BoraExtractorFan(BoraEntity, FanEntity):
    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "extractor",
            "Extractor",
            extractor_settings,
            control=True,
            requires=lambda coord: bool(
                {1, 2}.intersection(
                    descriptor(coord, "extractor_descriptor").get("extractor_mode_types", [])
                )
            ),
        )
        features = FanEntityFeature.TURN_ON
        if 0 in self._levels and 2 in self._mode_types:
            features |= FanEntityFeature.TURN_OFF
        if self._manual_levels and 2 in self._mode_types:
            features |= FanEntityFeature.SET_SPEED
        if self.preset_modes:
            features |= FanEntityFeature.PRESET_MODE
        self._attr_supported_features = features

    @property
    def _mode_types(self):
        return descriptor(self.coordinator, "extractor_descriptor").get("extractor_mode_types", [])

    @property
    def _levels(self):
        return levels(self.coordinator, "extractor_descriptor")

    @property
    def _manual_levels(self):
        return sorted(
            index for index, label in self._levels.items() if index > 0 and label.isdecimal()
        )

    @property
    def _special_levels(self):
        options = option_labels(
            {
                index: label
                for index, label in self._levels.items()
                if index > 0 and not label.isdecimal()
            }
        )
        return {
            index: (label if label != "auto" else f"auto ({index})")
            for index, label in options.items()
        }

    @property
    def _mode(self):
        return nested(self.snapshot, "extractor_mode", "mode")

    @property
    def _level(self):
        return nested(self.snapshot, "extractor_mode", "power_level")

    @property
    def is_on(self):
        if self._mode == "auto":
            return True
        return None if self._level is None else self._level > 0

    @property
    def speed_count(self):
        return len(self._manual_levels) or 1

    @property
    def percentage(self):
        if self._mode != "power_level" or self._level is None:
            return None
        if self._level == 0:
            return 0
        if self._level in self._special_levels:
            return 100
        if self._level not in self._manual_levels:
            return None
        return int(100 * (self._manual_levels.index(self._level) + 1) / len(self._manual_levels))

    @property
    def preset_modes(self):
        options = ["auto"] if 1 in self._mode_types else []
        return options + (list(self._special_levels.values()) if 2 in self._mode_types else [])

    @property
    def preset_mode(self):
        return "auto" if self._mode == "auto" else self._special_levels.get(self._level)

    @property
    def extra_state_attributes(self):
        return {"power_level": self._level, "level_label": self._levels.get(self._level)}

    async def async_set_percentage(self, percentage):
        if (
            isinstance(percentage, bool)
            or not isinstance(percentage, (int, float))
            or not math.isfinite(percentage)
            or not 0 <= percentage <= 100
        ):
            raise HomeAssistantError("Fan percentage must be between 0 and 100")
        if 2 not in self._mode_types:
            raise HomeAssistantError("Manual extractor power is not advertised")
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self._manual_levels:
            raise HomeAssistantError("No manual extractor levels are advertised")
        index = (
            min(math.ceil(percentage * len(self._manual_levels) / 100), len(self._manual_levels))
            - 1
        )
        await self._execute(
            extractor.set_power_level(self._manual_levels[index], allowed_levels=self._levels)
        )

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in self.preset_modes:
            raise HomeAssistantError("Extractor preset is not advertised")
        if preset_mode == "auto":
            await self._execute(extractor.set_auto_mode())
        else:
            level = next(
                index for index, label in self._special_levels.items() if label == preset_mode
            )
            await self._execute(extractor.set_power_level(level, allowed_levels=self._levels))

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        elif self._mode == "auto" or not self._manual_levels or 2 not in self._mode_types:
            await self.async_set_preset_mode("auto")
        else:
            level = self._level if self._level in self._manual_levels else self._manual_levels[0]
            await self._execute(extractor.set_power_level(level, allowed_levels=self._levels))

    async def async_turn_off(self, **kwargs):
        if 2 not in self._mode_types or 0 not in self._levels:
            raise HomeAssistantError("Extractor off is not advertised")
        await self._execute(extractor.set_power_level(0, allowed_levels=self._levels))


def build_entities(coordinator):
    modes = descriptor(coordinator, "extractor_descriptor").get("extractor_mode_types", [])
    if 1 not in modes and 2 not in modes:
        return []
    return [BoraExtractorFan(coordinator)]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(build_entities(entry.runtime_data))
