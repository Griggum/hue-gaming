"""Compatibility imports and runner for the original WoW client."""

from functools import partial

from hue_capture.auto import run as shared_run
from hue_games.wow import AutoSession
from hue_games.wow_unknown import UnknownLocationLogger

__all__ = ["AutoSession", "run"]


def run(
    config,
    matcher,
    calibration_path,
    controller=None,
    duration=0,
    seed=None,
    lighting=None,
    unknown_path=None,
    game_name="WoW",
    command_name="wow-hue",
):
    logger = (
        UnknownLocationLogger(unknown_path, config.unknown_capture)
        if unknown_path and config.unknown_capture.enabled
        else None
    )
    return shared_run(
        config,
        matcher,
        calibration_path,
        controller,
        duration,
        seed,
        lighting,
        game_name=game_name,
        command_name=command_name,
        session_factory=partial(AutoSession, unknown_logger=logger),
    )
