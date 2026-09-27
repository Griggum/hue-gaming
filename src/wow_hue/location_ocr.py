"""Compatibility imports for WoW matching and configuration."""

from hue_capture.location_ocr import Calibration, Detector, Match, Matcher, load_aliases
from hue_games.wow import OCRConfig, load_detection

__all__ = [
    "Calibration",
    "Detector",
    "Match",
    "Matcher",
    "OCRConfig",
    "load_aliases",
    "load_detection",
]
