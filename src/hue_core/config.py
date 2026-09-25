import os
import re
from pathlib import Path
from uuid import UUID

import yaml
from dotenv import dotenv_values

from .models import CHANNELS


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


def credentials(path: Path) -> tuple[str | None, str | None]:
    values = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
    key = os.getenv("HUE_USERNAME") or values.get("HUE_USERNAME")
    host = os.getenv("HUE_BRIDGE_IP") or values.get("HUE_BRIDGE_IP")
    return key, host


def load_mapping(path: Path, complete: bool = True) -> dict[str, str]:
    raw = read_yaml(path) if path.exists() else {}
    return validate_mapping(raw, complete)


def validate_mapping(raw, complete: bool = True) -> dict[str, str]:
    if not isinstance(raw, dict) or set(raw) - set(CHANNELS):
        raise ValueError("Light mapping contains unknown logical channels")
    if complete and set(raw) != set(CHANNELS):
        raise ValueError("Map all five channels with `wow-hue map CHANNEL RESOURCE_ID` first")
    if any(not isinstance(value, str) for value in raw.values()):
        raise ValueError("Light resource IDs must be UUID strings")
    raw = {channel: str(UUID(value)) for channel, value in raw.items()}
    if len(set(raw.values())) != len(raw):
        raise ValueError("Each logical channel must use a different Hue light")
    return raw
