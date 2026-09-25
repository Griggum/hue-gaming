"""Versioned scene library: game events reference reusable scenes by ID."""

import os
import tempfile
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .config import normalize
from .models import Model, Scene

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)]


class EventMapping(Model):
    scene: Identifier
    names: list[str] = Field(min_length=1)
    map_ids: list[int] = Field(default_factory=list)
    category: str = "zone"


class Game(Model):
    name: str = Field(min_length=1, max_length=160)
    events: dict[Identifier, EventMapping]


class Library(Model):
    schema_version: Literal[1] = 1
    revision: int = Field(default=1, ge=1)
    scenes: dict[Identifier, Scene] = Field(min_length=1)
    games: dict[Identifier, Game] = Field(default_factory=dict)

    @model_validator(mode="after")
    def references(self):
        for game in self.games.values():
            aliases, maps = {}, set()
            for event_id, event in game.events.items():
                if event.scene not in self.scenes:
                    raise ValueError(f"Unknown scene: {event.scene}")
                for name in [event_id, *event.names]:
                    alias = normalize(name)
                    if not alias or (alias in aliases and aliases[alias] != event_id):
                        raise ValueError(f"Blank or ambiguous event name: {name}")
                    aliases[alias] = event_id
                for map_id in event.map_ids:
                    if map_id in maps:
                        raise ValueError(f"Ambiguous map ID: {map_id}")
                    maps.add(map_id)
        return self

    def resolve(self, game_id: str, event_name: str) -> str | None:
        game = self.games.get(game_id)
        if game:
            for key, event in game.events.items():
                if normalize(event_name) in {normalize(n) for n in [key, *event.names]}:
                    return event.scene
        return None


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
