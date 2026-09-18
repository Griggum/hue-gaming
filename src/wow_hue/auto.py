import json
import logging
import math
import time
from dataclasses import asdict

from .ambient import AmbientEngine
from .config import read_yaml
from .location_ocr import Calibration, Detector


class AutoSession:
    """Only a confirmed parent change replaces the running ambient engine."""

    def __init__(self, matcher, controller=None, seed=None, lighting=None):
        self.detector = Detector(matcher)
        self.controller, self.seed = controller, seed
        self.engine = None
        self.lighting = lighting

    def observe(self, raw, confidence, now):
        match, changed = self.detector.observe(raw, confidence)
        if changed:
            self.engine = AmbientEngine(
                self.detector.matcher.catalog.profiles[match.profile], self.seed, self.lighting
            )
            if self.controller:
                self.controller.pending.clear()
        self.tick(now)
        return match, changed

    def tick(self, now):
        if self.engine:
            targets = self.engine.step(now)
            if self.controller:
                self.controller.submit(targets)
                self.controller.flush(now)


def run(config, matcher, calibration_path, controller=None, duration=0, seed=None, lighting=None):
    import mss

    from .screen import GameWindow, LocalOCR, capture

    if duration < 0 or not math.isfinite(duration):
        raise ValueError("Duration must be finite and nonnegative")
    if not calibration_path.exists():
        raise ValueError("Run `wow-hue calibrate` first to select the minimap location label")
    calibration = Calibration.model_validate(read_yaml(calibration_path))
    window_source, ocr = GameWindow(config.process_names), LocalOCR()
    session = AutoSession(matcher, controller, seed, lighting)
    started = time.monotonic()
    last_status = None
    last_log = 0
    print("OCR running locally. Switch to WoW. Ctrl+C pauses lighting updates.", flush=True)
    with mss.mss() as sct:
        while not duration or time.monotonic() - started < duration:
            now = time.monotonic()
            window = window_source.foreground()
            if window is None:
                session.detector.reset_candidate()
                status = {
                    "status": "paused: WoW is not foreground",
                    "profile": session.detector.confirmed,
                }
            else:
                image = capture(sct, window, calibration)
                raw, confidence = ocr.read(image)
                # Discard a frame if focus or window position changed during OCR.
                if window_source.foreground() != window:
                    session.detector.reset_candidate()
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
                    "profile": session.detector.confirmed,
                    "hue": "dry-run"
                    if controller is None
                    else "retrying"
                    if controller.pending
                    else "connected",
                }
            if status != last_status:
                print(json.dumps(status, ensure_ascii=False), flush=True)
                if now - last_log >= 5 or status.get("status") == "confirmed":
                    logging.getLogger(__name__).info(
                        "ocr_status %s", json.dumps(status, ensure_ascii=False)
                    )
                    last_log = now
                last_status = status
            time.sleep(max(0, 1 / config.samples_per_second - (time.monotonic() - now)))
    return 0
