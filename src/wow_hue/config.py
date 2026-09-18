import os
import re
from pathlib import Path
from uuid import UUID

import yaml
from dotenv import dotenv_values

from .models import CHANNELS, AppConfig, Profile


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently discarding user configuration."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        return yaml.load(stream, Loader=UniqueLoader)


def normalize(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


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
    catalog = Catalog(read_yaml(path.parent / config.profiles))
    return config, catalog


def credentials(path: Path) -> tuple[str | None, str | None]:
    values = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
    key = os.getenv("HUE_USERNAME") or values.get("HUE_USERNAME")
    host = os.getenv("HUE_BRIDGE_IP") or values.get("HUE_BRIDGE_IP")
    return key, host


def load_mapping(path: Path, complete: bool = True) -> dict[str, str]:
    raw = read_yaml(path) if path.exists() else {}
    if not isinstance(raw, dict) or set(raw) - set(CHANNELS):
        raise ValueError("Light mapping contains unknown logical channels")
    if complete and set(raw) != set(CHANNELS):
        raise ValueError("Map all five channels with `wow-hue map CHANNEL RESOURCE_ID` first")
    for value in raw.values():
        UUID(value)
    if len(set(raw.values())) != len(raw):
        raise ValueError("Each logical channel must use a different Hue light")
    return raw
