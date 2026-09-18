"""Local matching and debouncing, independent of capture and Hue."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from pydantic import Field

from .config import normalize, read_yaml
from .models import Model


class OCRConfig(Model):
    aliases_file: str = "location_aliases.yaml"
    calibration_file: str = "ocr.local.yaml"
    process_names: list[str] = Field(
        default_factory=lambda: ["WowClassic.exe", "Wow.exe"], min_length=1
    )
    samples_per_second: float = Field(default=3, ge=2, le=4)
    consecutive_reads: int = Field(default=3, ge=2, le=10)
    minimum_ocr_confidence: float = Field(default=0.65, ge=0, le=1)
    minimum_match_score: float = Field(default=0.84, ge=0.5, le=1)
    ambiguity_margin: float = Field(default=0.08, ge=0, le=1)


class Calibration(Model):
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=20, le=1000)
    height: int = Field(ge=10, le=300)
    client_width: int = Field(gt=0)
    client_height: int = Field(gt=0)

    def rectangle(self, width, height):
        if (width, height) != (self.client_width, self.client_height):
            raise ValueError("WoW window size changed; recalibrate the minimap label")
        if self.left + self.width > width or self.top + self.height > height:
            raise ValueError("Minimap ROI extends outside the game window")
        return self.left, self.top, self.width, self.height


@dataclass(frozen=True)
class Match:
    raw_location: str
    matched: str
    profile: str
    resolved_location: str
    confidence: float
    ocr_confidence: float


class Matcher:
    def __init__(self, catalog, aliases, config):
        self.catalog, self.config = catalog, config
        self.names = {}
        for key, profile in catalog.profiles.items():
            if profile.type == "neutral":
                continue
            for name in profile.names:
                self.add(name, key)
        if not isinstance(aliases, dict) or set(aliases) != {"location_aliases"}:
            raise ValueError("Alias file must contain location_aliases")
        for name, definition in aliases["location_aliases"].items():
            if not isinstance(definition, dict) or set(definition) != {"parent"}:
                raise ValueError(f"Alias {name} must define one parent")
            key = catalog.resolve(definition["parent"])
            if key is None or catalog.profiles[key].type == "neutral":
                raise ValueError(f"Unknown parent profile for alias {name}")
            self.add(name, key)

    def add(self, name, key):
        normalized = normalize(name)
        if not normalized:
            raise ValueError("Empty location alias")
        if normalized in self.names and self.names[normalized][1] != key:
            raise ValueError(f"Ambiguous location alias: {name}")
        self.names[normalized] = (name, key)

    def match(self, raw, confidence):
        text = normalize(raw)
        if len(text) < 4 or confidence < self.config.minimum_ocr_confidence:
            return None
        if text in self.names:
            display, key = self.names[text]
            return Match(raw, display, key, self.catalog.profiles[key].names[0], 1.0, confidence)
        ranked = sorted(
            (
                (SequenceMatcher(None, text, name).ratio(), display, key)
                for name, (display, key) in self.names.items()
            ),
            reverse=True,
        )
        if not ranked:
            return None
        score, display, key = ranked[0]
        competitor = next((s for s, _, k in ranked if k != key), 0)
        if (
            score < self.config.minimum_match_score
            or score - competitor < self.config.ambiguity_margin
        ):
            return None
        return Match(raw, display, key, self.catalog.profiles[key].names[0], score, confidence)


class Detector:
    def __init__(self, matcher):
        self.matcher = matcher
        self.candidate = None
        self.count = 0
        self.confirmed = None

    def reset_candidate(self):
        self.candidate, self.count = None, 0

    def observe(self, raw, confidence):
        match = self.matcher.match(raw, confidence)
        if match is None:
            self.reset_candidate()
            return None, False
        # Stabilize the resolved lighting location; subzones share a scene.
        if match.profile == self.candidate:
            self.count += 1
        else:
            self.candidate, self.count = match.profile, 1
        changed = (
            self.count >= self.matcher.config.consecutive_reads and self.confirmed != match.profile
        )
        if changed:
            self.confirmed = match.profile
        return match, changed


def load_detection(path, catalog):
    config = OCRConfig.model_validate(read_yaml(path))
    matcher = Matcher(catalog, read_yaml(path.parent / config.aliases_file), config)
    return config, matcher
