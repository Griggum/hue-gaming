"""Explicit game adapters. Shared capture never imports a game implementation."""

from dataclasses import dataclass
from importlib import import_module

from hue_capture.auto import AutoSession
from hue_capture.location_ocr import load_detection


@dataclass(frozen=True)
class GameAdapter:
    name: str
    default_config: str
    profile_format: str = "library"
    extension: str | None = None

    def load_detection(self, path, catalog):
        if self.extension:
            return import_module(self.extension).load_detection(path, catalog)
        return load_detection(path, catalog)

    def session_factory(self, path, config):
        if self.extension:
            return import_module(self.extension).session_factory(path, config)
        return AutoSession


GAMES = {
    "wow": GameAdapter("WoW", "config/app.yaml", "legacy", "hue_games.wow"),
    "valheim": GameAdapter("Valheim", "config/valheim.yaml"),
}


def game_ids():
    return tuple(GAMES)


def get_game(game_id):
    try:
        return GAMES[game_id]
    except KeyError:
        raise ValueError(f"Unsupported game: {game_id}") from None
