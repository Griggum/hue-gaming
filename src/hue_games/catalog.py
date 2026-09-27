import re

from hue_core.catalog import Library
from hue_core.config import normalize

from .models import Profile


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


def game_catalog(library: Library, game_id: str):
    game = library.games.get(game_id)
    if not game or not game.events:
        raise ValueError(f"The library has no {game_id} mappings")
    return Catalog(
        {
            "locations": {
                key: dict(
                    **library.scenes[event.scene].model_dump(),
                    names=event.names,
                    map_ids=event.map_ids,
                    type=event.category,
                )
                for key, event in game.events.items()
            }
        }
    )
