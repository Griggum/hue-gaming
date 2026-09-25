"""WoW migration and shared-library adapters; game metadata stays here."""

from pathlib import Path

from hue_core.catalog import Library, atomic_write


def import_wow(raw: dict) -> Library:
    # Migration is intentionally explicit; server restarts never overwrite edits.
    from wow_hue.config import Catalog

    catalog = Catalog(raw)
    scenes, events = {}, {}
    for key, profile in catalog.profiles.items():
        scene_id = "wow_" + key
        scene = profile.model_dump(exclude={"names", "map_ids", "type"})
        scene["name"] = profile.names[0]
        scenes[scene_id] = scene
        events[key] = {
            "scene": scene_id,
            "names": profile.names,
            "map_ids": profile.map_ids,
            "category": profile.type,
        }
    return Library.model_validate(
        {"scenes": scenes, "games": {"wow": {"name": "World of Warcraft", "events": events}}}
    )


def wow_catalog(library: Library):
    from wow_hue.config import Catalog

    game = library.games.get("wow")
    if not game or not game.events:
        raise ValueError("The library has no WoW mappings")
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


def migrate(source: Path, destination: Path):
    from hue_core.config import read_yaml

    if destination.exists():
        raise ValueError("Destination already exists; refusing to overwrite")
    library = import_wow(read_yaml(source))
    atomic_write(destination, library.model_dump_json(indent=2))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import legacy WoW profiles into a scene library")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    migrate(args.source, args.destination)
