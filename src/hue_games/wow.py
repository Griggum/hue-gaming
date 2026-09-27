"""WoW vocabulary and unknown-subzone discovery policy."""

from functools import partial

from pydantic import Field, model_validator

from hue_capture.auto import AutoSession as BaseSession
from hue_capture.location_ocr import OCRConfig as BaseOCRConfig
from hue_capture.location_ocr import load_detection as load_shared

from .wow_unknown import UnknownCaptureConfig, UnknownLocationLogger


class OCRConfig(BaseOCRConfig):
    process_names: list[str] = Field(
        default_factory=lambda: ["WowClassic.exe", "Wow.exe"], min_length=1
    )
    unknown_capture: UnknownCaptureConfig = Field(default_factory=UnknownCaptureConfig)

    @model_validator(mode="after")
    def parent_ttl(self):
        self.parent_context_soft_ttl_seconds = self.unknown_capture.parent_context_soft_ttl_seconds
        return self


def load_detection(path, catalog):
    return load_shared(path, catalog, OCRConfig)


class AutoSession(BaseSession):
    def __init__(self, matcher, controller=None, seed=None, lighting=None, unknown_logger=None):
        super().__init__(matcher, controller, seed, lighting)
        self.unknown_logger = unknown_logger

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


def session_factory(path, config):
    logger = (
        UnknownLocationLogger(
            path.parent / config.unknown_capture.output_file, config.unknown_capture
        )
        if config.unknown_capture.enabled
        else None
    )
    return partial(AutoSession, unknown_logger=logger)
