import json
import logging
import math
import time
from dataclasses import asdict

from hue_core.ambient import AmbientEngine
from hue_core.config import read_yaml

from .location_ocr import Calibration, Detector


class AutoSession:
    """Only a confirmed parent change replaces the running ambient engine."""

    def __init__(self, matcher, controller=None, seed=None, lighting=None):
        self.detector = Detector(matcher)
        self.controller, self.seed = controller, seed
        self.engine = None
        self.lighting = lighting
        self.active_profile = None

    def activate(self, profile):
        if self.active_profile == profile:
            return
        self.active_profile = profile
        self.engine = AmbientEngine(
            self.detector.matcher.catalog.profiles[profile], self.seed, self.lighting
        )
        if self.controller:
            self.controller.pending.clear()

    def pause(self):
        self.detector.reset_candidate()

    def observe(self, raw, confidence, now):
        match, changed = self.detector.observe(raw, confidence, now)
        if match and self.detector.count >= self.detector.matcher.config.consecutive_reads:
            self.activate(match.profile)
        self.tick(now)
        return match, changed

    def tick(self, now):
        if self.engine:
            targets = self.engine.step(now)
            if self.controller:
                self.controller.submit(targets)
                self.controller.flush(now)


def run(
    config,
    matcher,
    calibration_path,
    controller=None,
    duration=0,
    seed=None,
    lighting=None,
    game_name="the game",
    command_name="hue-client",
    session_factory=AutoSession,
):
    import mss

    from .screen import GameWindow, LocalOCR, capture

    if duration < 0 or not math.isfinite(duration):
        raise ValueError("Duration must be finite and nonnegative")
    if not calibration_path.exists():
        raise ValueError(
            f"Run `{command_name} calibrate` first to select the minimap location label"
        )
    calibration = Calibration.model_validate(read_yaml(calibration_path))
    window_source, ocr = GameWindow(config.process_names), LocalOCR()
    session = session_factory(matcher, controller, seed, lighting)
    started = time.monotonic()
    last_status = None
    last_log = 0
    print(
        f"OCR running locally. Switch to {game_name}. Ctrl+C pauses lighting updates.", flush=True
    )
    with mss.mss() as sct:
        while not duration or time.monotonic() - started < duration:
            now = time.monotonic()
            window = window_source.foreground()
            if window is None:
                session.pause()
                status = {
                    "status": f"paused: {game_name} is not foreground",
                    "profile": session.active_profile,
                }
            else:
                image = capture(sct, window, calibration)
                raw, confidence = ocr.read(image)
                # Discard a frame if focus or window position changed during OCR.
                if window_source.foreground() != window:
                    session.pause()
                    continue
                match, changed = session.observe(raw, confidence, now)
                status = {
                    "status": "confirmed"
                    if changed
                    else "reading"
                    if match
                    else "unknown; holding scene",
                    "raw_location": raw,
                    "match": asdict(match) if match else None,
                    "consecutive_reads": min(session.detector.count, config.consecutive_reads),
                    "profile": session.active_profile,
                    "hue": "dry-run"
                    if controller is None
                    else "retrying"
                    if controller.pending
                    else "connected",
                }
            if status != last_status:
                print(json.dumps(status, ensure_ascii=False), flush=True)
                if now - last_log >= 5 or status.get("status") == "confirmed":
                    log = logging.getLogger(__name__)
                    writer = log.info if status.get("status") == "confirmed" else log.debug
                    writer("ocr_status %s", json.dumps(status, ensure_ascii=False))
                    last_log = now
                last_status = status
            time.sleep(max(0, 1 / config.samples_per_second - (time.monotonic() - now)))
    return 0
