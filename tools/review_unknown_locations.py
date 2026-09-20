"""Consolidate local discoveries or print a proposed, validated alias change."""

import argparse
from pathlib import Path

import yaml

from wow_hue.config import load_config
from wow_hue.location_ocr import Matcher, load_aliases, load_detection
from wow_hue.unknown_locations import UnknownLocationIndex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/app.yaml"))
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("--parent")
    summary.add_argument("--output", type=Path)
    promote = commands.add_parser(
        "promote", help="Print proposed YAML only; does not modify registry"
    )
    promote.add_argument("--name", required=True)
    promote.add_argument("--parent", required=True)
    promote.add_argument("--profile", help="Optional dedicated lighting profile ID")
    args = parser.parse_args()
    app, catalog = load_config(args.config)
    ocr_path = args.config.resolve().parent / app.ocr
    config, _ = load_detection(ocr_path, catalog)
    if args.command == "promote":
        proposed = {"parent": args.parent}
        if args.profile:
            proposed["profile"] = args.profile
        aliases = load_aliases(ocr_path, config)
        if args.name in aliases["location_aliases"]:
            raise ValueError("Alias already exists; review its existing mapping manually")
        aliases["location_aliases"][args.name] = proposed
        Matcher(catalog, aliases, config)
        print(
            yaml.safe_dump(
                {"location_aliases": {args.name: proposed}}, sort_keys=False, allow_unicode=True
            )
        )
        return
    index = UnknownLocationIndex().load(ocr_path.parent / config.unknown_capture.output_file)
    data = index.summary()
    if args.parent:
        parent = catalog.resolve(args.parent)
        if parent is None:
            raise ValueError("Unknown parent profile")
        data["unknown_locations"] = {
            k: v for k, v in data["unknown_locations"].items() if v["parent_profile"] == parent
        }
    output = args.output or ocr_path.parent / "unknown_locations.generated.yaml"
    protected = {
        ocr_path.resolve(),
        (ocr_path.parent / config.aliases_file).resolve(),
        (args.config.resolve().parent / app.profiles).resolve(),
        (ocr_path.parent / config.unknown_capture.output_file).resolve(),
        args.config.resolve(),
    }
    if output.resolve() in protected:
        raise ValueError(
            "Review output must not overwrite runtime inputs or the canonical registry"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(
        f"{len(data['unknown_locations'])} candidates; {index.skipped_lines} malformed lines skipped. Wrote {output}"
    )


if __name__ == "__main__":
    main()
