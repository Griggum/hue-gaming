import argparse
import json
import logging
import math
import time
from dataclasses import asdict
from pathlib import Path

import yaml
from pydantic import ValidationError

from .ambient import AmbientEngine
from .config import credentials, load_config, load_mapping
from .hue import Bridge, BridgeError, Controller, discover
from .logging_setup import configure
from .models import CHANNELS, LightingConfig


def parser():
    root = argparse.ArgumentParser(description="Curated five-light Hue ambience")
    root.add_argument("--config", type=Path, default=Path("config/app.yaml"))
    root.add_argument("--bridge", help="Override the bridge's private LAN IP")
    root.add_argument(
        "--insecure",
        action="store_true",
        help="Disable Bridge certificate verification (diagnostics only)",
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate configuration and profiles offline")
    commands.add_parser("profiles", help="List available profiles")
    commands.add_parser("discover", help="Discover bridge IPs using Hue's discovery service")
    commands.add_parser("lights", help="Read bridge light IDs and capabilities")
    commands.add_parser("calibrate", help="Select minimap text ROI on the visible WoW window")
    for name in ("ocr", "auto"):
        command = commands.add_parser(
            name, help="Local minimap OCR debug" if name == "ocr" else "OCR-driven Hue ambience"
        )
        command.add_argument("--duration", type=float, default=0)
        command.add_argument("--seed", type=int)
        command.add_argument("--dry-run", action="store_true")
    mapping = commands.add_parser("map", help="Persist one logical light assignment")
    mapping.add_argument("channel", choices=CHANNELS)
    mapping.add_argument("resource_id")
    for name in ("profile", "ambient"):
        command = commands.add_parser(
            name,
            help="Preview or apply a profile"
            if name == "profile"
            else "Run independent ambient motion",
        )
        command.add_argument("name")
        command.add_argument("--seed", type=int)
        command.add_argument("--dry-run", action="store_true")
        if name == "ambient":
            command.add_argument(
                "--duration", type=float, default=0, help="Seconds to run; 0 runs until Ctrl+C"
            )
    for name in ("profile", "ambient", "ocr", "auto"):
        command = commands.choices[name]
        command.add_argument("--brightness", type=float, help="Master brightness multiplier, 0–1")
        command.add_argument(
            "--intensity", type=float, help="Motion variation, 0–1; 0 holds a stable target"
        )
        command.add_argument("--speed", type=float, help="Motion speed multiplier, 0.25–2")
    return root


def execute(args):
    if args.command == "discover":
        print(json.dumps(discover(), indent=2))
        return 0
    config, catalog = load_config(args.config)
    tuning = config.lighting.model_dump()
    for option in ("brightness", "intensity", "speed"):
        value = getattr(args, option, None)
        if value is not None:
            tuning[option] = value
    config.lighting = LightingConfig.model_validate(tuning)
    base = args.config.resolve().parent
    if args.command in ("validate", "calibrate", "ocr", "auto"):
        from .location_ocr import load_detection

        ocr_path = base / config.ocr
        ocr_config, matcher = load_detection(ocr_path, catalog)
        calibration_path = ocr_path.parent / ocr_config.calibration_file
    if args.command == "calibrate":
        from .screen import calibrate

        calibrate(calibration_path, ocr_config.process_names)
        return 0
    if args.command in ("ocr", "auto"):
        if args.duration < 0 or not math.isfinite(args.duration):
            raise ValueError("Duration must be finite and nonnegative")
        from .auto import run

        configure(base / config.log_file)
        if args.command == "ocr" or args.dry_run:
            return run(
                ocr_config,
                matcher,
                calibration_path,
                duration=args.duration,
                seed=args.seed,
                lighting=config.lighting,
                unknown_path=ocr_path.parent / ocr_config.unknown_capture.output_file,
            )
    if args.command in ("validate", "profiles"):
        if args.command == "validate":
            load_mapping(base / config.lights, complete=False)
            print(
                f"Configuration valid; {len(catalog.profiles)} profiles. Bridge and mapping completeness not checked."
            )
        else:
            for key, value in catalog.profiles.items():
                print(f"{key:38} {value.motion:8} {value.effect:8} {value.names[0]}")
        return 0
    engine = None
    if args.command in ("profile", "ambient"):
        key = catalog.resolve(args.name)
        if key is None:
            raise ValueError(f"Unknown profile: {args.name}. Run `wow-hue profiles`.")
        if args.command == "ambient" and (args.duration < 0 or not math.isfinite(args.duration)):
            raise ValueError("Duration must be finite and nonnegative")
        engine = AmbientEngine(catalog.profiles[key], args.seed, config.lighting)
        targets = engine.step(time.monotonic())
        if args.dry_run:
            print(json.dumps({c: asdict(t) for c, t in targets.items()}, indent=2))
            return 0
    application_key, env_host = credentials(base / config.env_file)
    if not application_key:
        raise ValueError("Set HUE_USERNAME in .env or the environment")
    host = args.bridge or config.bridge.host or env_host
    if not host:
        raise ValueError(
            "Set HUE_BRIDGE_IP in .env or use --bridge IP; `wow-hue discover` lists bridges"
        )
    if config.bridge.ca_file:
        config.bridge.ca_file = str(base / config.bridge.ca_file)
    configure(base / config.log_file)
    bridge = Bridge(host, application_key, config.bridge, insecure=args.insecure)
    try:
        resources = bridge.lights()
        if args.command == "lights":
            print(
                json.dumps(
                    [
                        {
                            "id": r["id"],
                            "name": r.get("metadata", {}).get("name", ""),
                            "color": "color" in r,
                            "dimming": "dimming" in r,
                        }
                        for r in resources
                    ],
                    indent=2,
                )
            )
            return 0
        if args.command == "map":
            mapping_path = base / config.lights
            mapping = load_mapping(mapping_path, complete=False)
            mapping[args.channel] = args.resource_id
            if len(set(mapping.values())) != len(mapping):
                raise ValueError("Resource already assigned to another channel")
            Controller(bridge, mapping, resources)
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = mapping_path.with_suffix(".yaml.tmp")
            temporary.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
            temporary.replace(mapping_path)
            print(f"Mapped {args.channel}; {len(mapping)}/5 channels configured.")
            return 0
        mapping = load_mapping(base / config.lights)
        controller = Controller(bridge, mapping, resources, config.bridge.max_retry_seconds)
        if args.command == "auto":
            return run(
                ocr_config,
                matcher,
                calibration_path,
                controller,
                args.duration,
                args.seed,
                config.lighting,
                unknown_path=ocr_path.parent / ocr_config.unknown_capture.output_file,
            )
        controller.submit(targets)
        started = time.monotonic()
        if args.command == "profile":
            if not controller.flush(started):
                raise BridgeError(
                    "Scene delivery incomplete; bridge unavailable. Run the command again to retry."
                )
            print(f"Applied {key} to five lights.")
            return 0
        print(
            f"Ambient: {key}. Ctrl+C pauses updates and leaves lights at their current state.",
            flush=True,
        )
        logging.getLogger(__name__).info("ambient_started profile=%s", key)
        while not args.duration or time.monotonic() - started < args.duration:
            now = time.monotonic()
            controller.submit(engine.step(now))
            controller.flush(now)
            time.sleep(0.25)
        if controller.pending:
            raise BridgeError(
                "Ambient session ended with undelivered targets; check bridge connection"
            )
        return 0
    finally:
        bridge.close()


def main():
    args = parser().parse_args()
    try:
        return execute(args)
    except KeyboardInterrupt:
        print("\nPaused. Lights retain their current state.")
        return 0
    except ValidationError as error:
        # Do not echo configuration inputs (which may contain sensitive values).
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        print(f"Configuration error: {details}")
        return 2
    except (BridgeError, ValueError, OSError, yaml.YAMLError) as error:
        print(f"Error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
