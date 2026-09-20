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

    def __init__(self, matcher, controller=None, seed=None, lighting=None, unknown_logger=None):
        self.detector = Detector(matcher)
        self.controller, self.seed = controller, seed
        self.engine = None
        self.lighting = lighting
        self.unknown_logger = unknown_logger
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
        if self.unknown_logger:
            self.unknown_logger.reset()

    def observe(self, raw, confidence, now):
        match, changed = self.detector.observe(raw, confidence, now)
        if match:
            if self.unknown_logger:
                self.unknown_logger.reset()
            if self.detector.count >= self.detector.matcher.config.consecutive_reads:
                self.activate(match.profile)
        elif self.unknown_logger:
            self.unknown_logger.observe(raw, confidence, now, self.detector, self.active_profile)
            known = self.detector.confirmed_match
            if (
                known
                and self.unknown_logger.detector.count
                >= self.unknown_logger.config.consecutive_reads
                and now - self.detector.parent_seen_at
                <= self.unknown_logger.config.parent_context_soft_ttl_seconds
            ):
                self.activate(known.parent_profile)
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
    unknown_path=None,
):
    import mss

    from .screen import GameWindow, LocalOCR, capture

    if duration < 0 or not math.isfinite(duration):
        raise ValueError("Duration must be finite and nonnegative")
    if not calibration_path.exists():
        raise ValueError("Run `wow-hue calibrate` first to select the minimap location label")
    calibration = Calibration.model_validate(read_yaml(calibration_path))
    window_source, ocr = GameWindow(config.process_names), LocalOCR()
    from .unknown_locations import UnknownLocationLogger

    unknown_logger = (
        UnknownLocationLogger(unknown_path, config.unknown_capture)
        if unknown_path and config.unknown_capture.enabled
        else None
    )
    session = AutoSession(matcher, controller, seed, lighting, unknown_logger)
    started = time.monotonic()
    last_status = None
    last_log = 0
    print("OCR running locally. Switch to WoW. Ctrl+C pauses lighting updates.", flush=True)
    with mss.mss() as sct:
        while not duration or time.monotonic() - started < duration:
            now = time.monotonic()
            window = window_source.foreground()
            if window is None:
                session.pause()
                status = {
                    "status": "paused: WoW is not foreground",
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
