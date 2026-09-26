"""Shared integration constants."""

from homeassistant.const import Platform

DOMAIN = "bora"
NAME = "BORA"
CONF_ENABLE_CONTROLS = "enable_controls"
CONF_ENABLE_COOKING = "enable_cooking_controls"
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BUTTON,
]
