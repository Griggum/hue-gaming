"""Manual/event-driven client for any game; only reads local profiles."""

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .ambient import AmbientEngine
from .catalog import Library
from .config import credentials, load_mapping
from .hue import Bridge, BridgeError, Controller
from .models import BridgeConfig, LightingConfig


def main():
    parser = argparse.ArgumentParser(description="Direct-to-Hue client for shared game presets")
    parser.add_argument("--cache", type=Path, default=Path("config/profiles.cache.json"))
    parser.add_argument("--lights", type=Path, default=Path("config/lights.yaml"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--ca-file")
    parser.add_argument("--bridge-id", help="16-character Hue Bridge ID for TLS verification")
    parser.add_argument("--game", help="Resolve the name as an event within this game")
    parser.add_argument("--ambient", action="store_true")
    parser.add_argument("--brightness", type=float, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("scene", nargs="?", help="Scene ID, or event name with --game")
    args = parser.parse_args()
    try:
        library = Library.model_validate_json(args.cache.read_text(encoding="utf-8"))
        if not args.scene:
            for key, scene in library.scenes.items():
                print(f"{key:45} {scene.name}")
            return 0
        key = library.resolve(args.game, args.scene) if args.game else args.scene
        if key not in library.scenes:
            raise ValueError("Unknown scene or game event")
        engine = AmbientEngine(
            library.scenes[key], lighting=LightingConfig(brightness=args.brightness)
        )
        targets = engine.step(time.monotonic())
        if args.dry_run:
            print(json.dumps({c: asdict(t) for c, t in targets.items()}, indent=2))
            return 0
        token, host = credentials(args.env_file)
        if not token or not host:
            raise ValueError("Set HUE_USERNAME and HUE_BRIDGE_IP")
        bridge = Bridge(
            host,
            token,
            BridgeConfig(ca_file=args.ca_file, bridge_id=args.bridge_id),
            insecure=args.insecure,
        )
        try:
            controller = Controller(bridge, load_mapping(args.lights), bridge.lights())
            controller.submit(targets)
            if not controller.flush(time.monotonic()) and not args.ambient:
                raise BridgeError("Scene delivery incomplete; retry when bridge is available")
            while args.ambient:
                time.sleep(0.25)
                now = time.monotonic()
                controller.submit(engine.step(now))
                controller.flush(now)
        finally:
            bridge.close()
        return 0
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, BridgeError):
        print("Unable to run: check local library, scene, light mapping and bridge configuration")
        return 1
