"""Local client configuration and cached profile loading for registered games."""

import logging
from pathlib import Path

from hue_core.catalog import Library
from hue_core.config import credentials, load_mapping, read_yaml

from .catalog import Catalog, game_catalog
from .models import AppConfig
from .registry import get_game

__all__ = ["credentials", "load_config", "load_mapping"]


def load_config(path: Path):
    config = AppConfig.model_validate(read_yaml(path))
    game = get_game(config.game)
    if config.profile_cache:
        try:
            candidate = game_catalog(
                Library.model_validate_json(
                    (path.parent / config.profile_cache).read_text(encoding="utf-8")
                ),
                config.game,
            )
            game.load_detection(path.parent / config.ocr, candidate)
            return config, candidate
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).warning(
                "Profile cache unavailable or incompatible; using bundled %s profiles", config.game
            )
    if game.profile_format == "library":
        catalog = game_catalog(
            Library.model_validate_json(
                (path.parent / config.profiles).read_text(encoding="utf-8")
            ),
            config.game,
        )
    else:
        catalog = Catalog(read_yaml(path.parent / config.profiles))
    return config, catalog
