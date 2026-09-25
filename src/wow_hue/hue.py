"""Compatibility exports; implementation lives in hue_core."""

from hue_core.hue import (
    AuthenticationError,
    Bridge,
    BridgeError,
    Controller,
    clip_to_gamut,
    discover,
    payload,
    rgb_to_xy,
)

__all__ = [
    "AuthenticationError",
    "Bridge",
    "BridgeError",
    "Controller",
    "clip_to_gamut",
    "discover",
    "payload",
    "rgb_to_xy",
]
