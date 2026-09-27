"""Compatibility imports for existing WoW scripts."""

from hue_core.config import UniqueLoader, credentials, load_mapping, normalize, read_yaml
from hue_games.catalog import Catalog
from hue_games.config import load_config

__all__ = [
    "Catalog",
    "UniqueLoader",
    "credentials",
    "load_config",
    "load_mapping",
    "normalize",
    "read_yaml",
]
