"""Untrusted, text-only discoveries. Never used to route lighting."""

import json
import logging
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import Field, model_validator

from .config import normalize
from .models import Model


class UnknownCaptureConfig(Model):
    enabled: bool = True
    output_file: str = "unknown_locations.jsonl"
    minimum_ocr_confidence: float = Field(default=0.75, ge=0, le=1)
    consecutive_reads: int = Field(default=3, ge=2, le=20)
    minimum_characters: int = Field(default=5, ge=3)
    repeat_suppression_seconds: float = Field(default=300, ge=1, allow_inf_nan=False)
    parent_context_soft_ttl_seconds: float = Field(default=60, ge=0, allow_inf_nan=False)
    parent_context_hard_ttl_seconds: float = Field(default=300, ge=0, allow_inf_nan=False)
    wow_product: str | None = None
    wow_build: str | None = None

    @model_validator(mode="after")
    def ttl_order(self):
        if self.parent_context_soft_ttl_seconds > self.parent_context_hard_ttl_seconds:
            raise ValueError("Parent soft TTL must not exceed hard TTL")
        return self


class UnknownDetector:
    def __init__(self, config):
        self.config = config
        self.recent = {}
        self.reset()

    def reset(self):
        self.candidate, self.count, self.first_seen = None, 0, None

    def observe(self, raw, confidence, parent, now, timestamp):
        text = normalize(raw)
        if (
            not self.config.enabled
            or not math.isfinite(confidence)
            or confidence < self.config.minimum_ocr_confidence
            or len(text) < self.config.minimum_characters
        ):
            self.reset()
            return None
        key = (parent, text)
        if key != self.candidate:
            self.candidate, self.count, self.first_seen = key, 0, timestamp
        self.count += 1
        self.recent = {
            k: t for k, t in self.recent.items() if now - t < self.config.repeat_suppression_seconds
        }
        if self.count < self.config.consecutive_reads or key in self.recent:
            return None
        self.recent[key] = now
        return {
            "first_seen": self.first_seen,
            "last_seen": timestamp,
            "raw_text": raw,
            "normalized_text": text,
            "ocr_confidence": confidence,
            "confirmation_reads": self.count,
        }


class UnknownLocationLogger:
    def __init__(self, path, config):
        self.path, self.config = Path(path), config
        self.detector = UnknownDetector(config)
        self.session_id = str(uuid4())

    def reset(self):
        self.detector.reset()

    def observe(self, raw, confidence, now, detector, active_profile=None):
        known = detector.confirmed_match
        age = max(0, now - detector.parent_seen_at) if known else None
        fresh = known is not None and age <= self.config.parent_context_hard_ttl_seconds
        parent = known.parent_profile if fresh else None
        timestamp = datetime.now(UTC).isoformat()
        record = self.detector.observe(raw, confidence, parent, now, timestamp)
        if record is None:
            return None
        record.update(
            schema_version=1,
            session_id=self.session_id,
            parent_context=known.parent_location if fresh else None,
            parent_profile=parent,
            parent_context_source="previous_confirmed" if fresh else "unknown",
            parent_context_age_seconds=age,
            parent_context_strength=(
                "strong" if age <= self.config.parent_context_soft_ttl_seconds else "weak"
            )
            if fresh
            else "unknown",
            previous_known_location=known.matched if known else None,
            previous_parent_profile=known.parent_profile if known else None,
            active_profile_at_detection=active_profile,
            match_result="unknown",
            wow_product=self.config.wow_product,
            wow_build=self.config.wow_build,
        )
        # Scores here are diagnostics only; they cannot promote or route anything.
        from difflib import SequenceMatcher

        candidates = [
            (SequenceMatcher(None, record["normalized_text"], name).ratio(), display)
            for name, (display, _) in detector.matcher.names.items()
        ]
        score, candidate = max(candidates, default=(0, None))
        record.update(best_known_candidate=candidate, best_known_match_score=score)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve later observations if a previous process left a partial line.
            needs_newline = False
            if self.path.exists() and self.path.stat().st_size:
                with self.path.open("rb") as previous:
                    previous.seek(-1, 2)
                    needs_newline = previous.read(1) != b"\n"
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(
                    ("\n" if needs_newline else "") + json.dumps(record, ensure_ascii=False) + "\n"
                )
            logging.getLogger(__name__).info(
                "unknown_location_confirmed text=%r parent=%s", raw, parent
            )
        except OSError:
            self.detector.recent.pop((parent, record["normalized_text"]), None)
            logging.getLogger(__name__).warning("unknown_location_write_failed")
        return record


class UnknownLocationIndex:
    def __init__(self):
        self.groups = {}
        self.skipped_lines = 0

    def load(self, path):
        if not Path(path).exists():
            return self
        with Path(path).open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    r = json.loads(line)
                    if r.get("schema_version") != 1:
                        raise ValueError("Unsupported observation")
                    key = (r["parent_profile"], r["normalized_text"])
                    if not isinstance(key[1], str) or not isinstance(r["raw_text"], str):
                        raise TypeError("Invalid text")
                    score = float(r["ocr_confidence"])
                    if not math.isfinite(score) or not 0 <= score <= 1:
                        raise ValueError("Invalid confidence")
                    r["ocr_confidence"] = score
                    for field in ("first_seen", "last_seen", "session_id"):
                        if not isinstance(r[field], str):
                            raise TypeError("Invalid metadata")
                    self.groups.setdefault(key, []).append(r)
                except (ValueError, KeyError, TypeError, AttributeError):
                    self.skipped_lines += 1
        return self

    def summary(self):
        result = {}
        for (parent, text), rows in sorted(self.groups.items(), key=lambda item: str(item[0])):
            variants = Counter(r["raw_text"] for r in rows)
            previous = Counter(
                r.get("previous_known_location") for r in rows if r.get("previous_known_location")
            )
            # JSON-encoded pair prevents punctuation-based key collisions.
            key = json.dumps([parent, text], ensure_ascii=False)
            result[key] = {
                "display_name": variants.most_common(1)[0][0],
                "normalized_name": text,
                "parent_profile": parent,
                "parent_context": rows[-1].get("parent_context"),
                "observations": len(rows),
                "sessions_seen": len({r["session_id"] for r in rows}),
                "first_seen": min(r["first_seen"] for r in rows),
                "last_seen": max(r["last_seen"] for r in rows),
                "confidence": {
                    "mean_ocr": sum(r["ocr_confidence"] for r in rows) / len(rows),
                    "minimum_ocr": min(r["ocr_confidence"] for r in rows),
                },
                "raw_variants": dict(variants),
                "context": {"previous_known_locations": dict(previous)},
                "status": "needs_review",
            }
        return {"unknown_locations": result}
