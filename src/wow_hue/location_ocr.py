"""Local matching and debouncing, independent of capture and Hue."""

import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from pydantic import Field

from .config import normalize, read_yaml
from .models import Model
from .unknown_locations import UnknownCaptureConfig


class OCRConfig(Model):
    registry_files: list[str] = Field(default_factory=list)
    unknown_capture: UnknownCaptureConfig = Field(default_factory=UnknownCaptureConfig)
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
    minimum_prefix_characters: int = Field(default=8, ge=5, le=40)
    minimum_prefix_fraction: float = Field(default=0.5, ge=0.25, le=1)
    minimum_prefix_similarity: float = Field(default=0.9, ge=0.8, le=1)


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
    match_method: str = "full"
    parent_profile: str | None = None
    parent_location: str | None = None


class Matcher:
    def __init__(self, catalog, aliases, config):
        self.catalog, self.config = catalog, config
        self.names = {}
        self.parents = {}
        self.scoped = {}
        for key, profile in catalog.profiles.items():
            if profile.type == "neutral":
                continue
            for name in profile.names:
                self.add(name, key)
        if not isinstance(aliases, dict) or set(aliases) != {"location_aliases"}:
            raise ValueError("Alias file must contain location_aliases")
        for name, definition in aliases["location_aliases"].items():
            definitions = definition if isinstance(definition, list) else [definition]
            if not definitions:
                raise ValueError(f"Empty scoped alias: {name}")
            for entry in definitions:
                if (
                    not isinstance(entry, dict)
                    or "parent" not in entry
                    or set(entry) - {"parent", "profile"}
                ):
                    raise ValueError(f"Alias {name} requires parent and optional profile")
                parent = catalog.resolve(entry["parent"])
                if parent is None or catalog.profiles[parent].type == "neutral":
                    raise ValueError(f"Unknown parent profile for alias {name}")
                target = entry.get("profile", parent)
                if target not in catalog.profiles or catalog.profiles[target].type == "neutral":
                    raise ValueError(f"Unknown lighting profile for alias {name}: {target}")
                normalized = normalize(name)
                if isinstance(definition, list):
                    if normalized in self.names or parent in self.scoped.get(normalized, {}):
                        raise ValueError(f"Ambiguous scoped alias: {name}")
                    self.scoped.setdefault(normalized, {})[parent] = (name, target)
                else:
                    self.add(name, target)
                self.parents[(normalized, target)] = parent

    def add(self, name, key):
        normalized = normalize(name)
        if not normalized:
            raise ValueError("Empty location alias")
        if normalized in self.names and self.names[normalized][1] != key:
            raise ValueError(f"Ambiguous location alias: {name}")
        self.names[normalized] = (name, key)

    def match(self, raw, confidence, parent_profile=None):
        text = normalize(raw)
        if len(text) < 4 or confidence < self.config.minimum_ocr_confidence:
            return None
        names = dict(self.names)
        for label, scopes in self.scoped.items():
            if parent_profile in scopes:
                names[label] = scopes[parent_profile]
        if text in self.scoped and text not in names:
            return None

        def result(display, key, score, method):
            parent = self.parents.get((normalize(display), key), key)
            if normalize(display) in self.scoped:
                parent = parent_profile
            return Match(
                raw,
                display,
                key,
                self.catalog.profiles[key].names[0],
                score,
                confidence,
                method,
                parent,
                self.catalog.profiles[parent].names[0],
            )

        if text in names:
            display, key = names[text]
            return result(display, key, 1.0, "full")
        # A shared literal prefix cannot identify a wing/zone even if one name
        # happens to be shorter and therefore scores better as a whole string.
        prefix_parents = {key for name, (_, key) in names.items() if name.startswith(text)}
        if len(prefix_parents) > 1:
            return None
        ranked = []
        for name, (display, key) in names.items():
            score = SequenceMatcher(None, text, name).ratio()
            method = "full"
            if (
                len(text) >= self.config.minimum_prefix_characters
                and len(text) < len(name)
                and len(text) / len(name) >= self.config.minimum_prefix_fraction
            ):
                similarity = SequenceMatcher(None, text, name[: len(text)]).ratio()
                # Prefix-only evidence is discounted versus a complete label.
                if (
                    similarity >= self.config.minimum_prefix_similarity
                    and similarity * 0.96 > score
                ):
                    score, method = similarity * 0.96, "prefix"
            ranked.append((score, display, key, method))
        ranked.sort(reverse=True)
        if not ranked:
            return None
        score, display, key, method = ranked[0]
        competitor = next((s for s, _, k, _ in ranked if k != key), 0)
        if (
            score < self.config.minimum_match_score
            or score - competitor < self.config.ambiguity_margin
        ):
            return None
        return result(display, key, score, method)


class Detector:
    def __init__(self, matcher):
        self.matcher = matcher
        self.candidate = None
        self.count = 0
        self.confirmed = None
        self.confirmed_match = None
        self.parent_seen_at = None

    def reset_candidate(self):
        self.candidate, self.count = None, 0

    def observe(self, raw, confidence, now=None):
        now = time.monotonic() if now is None else now
        parent = None
        if (
            self.confirmed_match
            and now - self.parent_seen_at
            <= self.matcher.config.unknown_capture.parent_context_soft_ttl_seconds
        ):
            parent = self.confirmed_match.parent_profile
        match = self.matcher.match(raw, confidence, parent)
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
        if self.count >= self.matcher.config.consecutive_reads:
            self.confirmed_match = match
            # Ambiguous scoped labels must not indefinitely renew their own context.
            if normalize(match.matched) not in self.matcher.scoped:
                self.parent_seen_at = now
        return match, changed


def load_detection(path, catalog):
    config = OCRConfig.model_validate(read_yaml(path))
    aliases = load_aliases(path, config)
    matcher = Matcher(catalog, aliases, config)
    return config, matcher


def load_aliases(path, config):
    merged = {}
    spellings = {}
    # Additional inventories first; hand-maintained aliases explicitly override them.
    for filename in [*config.registry_files, config.aliases_file]:
        raw = read_yaml(path.parent / filename)
        if (
            not isinstance(raw, dict)
            or set(raw) != {"location_aliases"}
            or not isinstance(raw["location_aliases"], dict)
        ):
            raise ValueError(f"Invalid alias registry: {filename}")
        for name, definition in raw["location_aliases"].items():
            normalized = normalize(name)
            previous = spellings.get(normalized)
            if previous is not None:
                if filename != config.aliases_file:
                    raise ValueError(f"Conflicting imported alias: {name}")
                del merged[previous]
            merged[name] = definition
            spellings[normalized] = name
    return {"location_aliases": merged}
