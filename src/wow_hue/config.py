import re
from pathlib import Path

from hue_core.config import UniqueLoader, credentials, load_mapping, normalize, read_yaml

from .models import AppConfig, Profile

__all__ = [
    "Catalog",
    "UniqueLoader",
    "credentials",
    "load_config",
    "load_mapping",
    "normalize",
    "read_yaml",
]


class Catalog:
    def __init__(self, raw):
        if not isinstance(raw, dict) or set(raw) != {"locations"}:
            raise ValueError("Profile file must contain a locations mapping")
        self.profiles = {}
        self.aliases = {}
        self.map_ids = {}
        for key, value in raw["locations"].items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ValueError(f"Invalid canonical ID: {key}")
            profile = Profile.model_validate(value)
            self.profiles[key] = profile
            for name in [key, *profile.names]:
                alias = normalize(name)
                if alias in self.aliases and self.aliases[alias] != key:
                    raise ValueError(f"Ambiguous alias: {name}")
                self.aliases[alias] = key
            for map_id in profile.map_ids:
                if map_id in self.map_ids:
                    raise ValueError(f"Ambiguous map ID: {map_id}")
                self.map_ids[map_id] = key
        if not self.profiles:
            raise ValueError("At least one profile is required")

    def resolve(self, name: str = "", map_id: int | None = None) -> str | None:
        return self.map_ids.get(map_id) or self.aliases.get(normalize(name))


def load_config(path: Path):
    config = AppConfig.model_validate(read_yaml(path))
    if config.profile_cache:
        import logging

        from hue_core.catalog import Library

        from .library import wow_catalog

        try:
            candidate = wow_catalog(
                Library.model_validate_json(
                    (path.parent / config.profile_cache).read_text(encoding="utf-8")
                )
            )
            # Validate against the local OCR registries before accepting a snapshot.
            from .location_ocr import load_detection

            load_detection(path.parent / config.ocr, candidate)
            return config, candidate
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).warning(
                "Profile cache unavailable or incompatible; using bundled WoW profiles"
            )
    return config, Catalog(read_yaml(path.parent / config.profiles))
