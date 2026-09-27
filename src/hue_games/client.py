"""Unified command entry point, preserving the original manual scene interface."""

from hue_core.client import main as manual_main
from hue_core.client import parser as manual_parser

from .cli import main as game_main

GAME_COMMANDS = {
    "calibrate",
    "ocr",
    "auto",
    "validate",
    "profiles",
    "profile",
    "ambient",
    "map",
    "lights",
    "discover",
}


def main(argv=None):
    preview, _ = manual_parser(add_help=False).parse_known_args(argv)
    if not preview.explicit_scene and preview.scene in GAME_COMMANDS:
        return game_main(argv=argv)
    return manual_main(argv)
