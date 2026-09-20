import json
from pathlib import Path

import pytest

from wow_hue.auto import AutoSession
from wow_hue.config import load_config
from wow_hue.location_ocr import Detector, Matcher, OCRConfig
from wow_hue.unknown_locations import (
    UnknownCaptureConfig,
    UnknownDetector,
    UnknownLocationIndex,
    UnknownLocationLogger,
)

ROOT = Path(__file__).resolve().parents[1]


def make_matcher():
    _, catalog = load_config(ROOT / "config/app.yaml")
    return Matcher(
        catalog,
        {
            "location_aliases": {
                "Fargodeep Mine": {"parent": "Elwynn Forest", "profile": "deadmines"},
                "Raven Hill Cemetery": {"parent": "Duskwood"},
                "Shared Shore": [{"parent": "Elwynn Forest"}, {"parent": "Westfall"}],
            }
        },
        OCRConfig(),
    )


def test_override_retains_parent():
    match = make_matcher().match("Fargodeep Mine", 1)
    assert match.profile == "deadmines"
    assert match.parent_profile == "elwynn_forest"
    assert match.parent_location == "Elwynn Forest"


def test_scoped_names_require_fresh_parent():
    matcher = make_matcher()
    assert matcher.match("Shared Shore", 1) is None
    assert matcher.match("Shared Shore", 1, "westfall").profile == "westfall"
    detector = Detector(matcher)
    for now in range(3):
        detector.observe("Westfall", 1, now)
    assert detector.observe("Shared Shore", 1, 10)[0].parent_profile == "westfall"
    assert detector.observe("Shared Shore", 1, 100)[0] is None


def test_invalid_profile_reference():
    matcher = make_matcher()
    with pytest.raises(ValueError, match="Unknown lighting profile"):
        Matcher(
            matcher.catalog,
            {"location_aliases": {"Mine": {"parent": "Elwynn Forest", "profile": "missing"}}},
            OCRConfig(),
        )


def test_unknown_stability_and_parent_scoped_suppression():
    detector = UnknownDetector(UnknownCaptureConfig())
    assert detector.observe("New Place", 0.9, "westfall", 0, "t0") is None
    assert detector.observe("noise", 0.1, "westfall", 1, "t1") is None
    for now in (2, 3):
        assert detector.observe("New Place", 0.9, "westfall", now, str(now)) is None
    assert detector.observe("New Place", 0.9, "westfall", 4, "t4")["first_seen"] == "2"
    assert detector.observe("New Place", 0.9, "westfall", 5, "t5") is None
    for now in (6, 7):
        assert detector.observe("New Place", 0.9, "duskwood", now, str(now)) is None
    assert detector.observe("New Place", 0.9, "duskwood", 8, "t8")


def test_session_records_context_holds_parent_and_restores_override(tmp_path):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    logger = UnknownLocationLogger(path, matcher.config.unknown_capture)
    session = AutoSession(matcher, unknown_logger=logger)
    for now in range(3):
        session.observe("Fargodeep Mine", 1, now)
    assert session.active_profile == "deadmines"
    for now in range(3, 6):
        session.observe("Uncharted Hollow", 0.95, now)
    assert session.active_profile == "elwynn_forest"
    record = json.loads(path.read_text())
    assert record["parent_profile"] == "elwynn_forest"
    assert record["parent_context_age_seconds"] == 3
    assert record["parent_context_source"] == "previous_confirmed"
    assert record["active_profile_at_detection"] == "deadmines"
    for now in range(6, 9):
        session.observe("Fargodeep Mine", 1, now)
    assert session.active_profile == "deadmines"
    session.pause()
    for now in (100, 101, 102):
        session.observe("Uncharted Cavern", 0.95, now)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[-1]["parent_context_strength"] == "weak"
    for now in (400, 401, 402):
        session.observe("Uncharted Summit", 0.95, now)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[-1]["parent_profile"] is None
    assert records[-1]["parent_context_source"] == "unknown"


def test_no_parent_and_malformed_last_line(tmp_path):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    session = AutoSession(
        matcher, unknown_logger=UnknownLocationLogger(path, matcher.config.unknown_capture)
    )
    for now in range(3):
        session.observe("Uncharted Place", 1, now)
    assert session.active_profile is None
    with path.open("a") as stream:
        stream.write("{broken")
    index = UnknownLocationIndex().load(path)
    assert index.skipped_lines == 1
    entry = next(iter(index.summary()["unknown_locations"].values()))
    assert entry["observations"] == 1
    assert entry["parent_profile"] is None
    assert entry["status"] == "needs_review"


def test_unknown_capture_disabled_and_pause(tmp_path):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    logger = UnknownLocationLogger(path, UnknownCaptureConfig(enabled=False))
    session = AutoSession(matcher, unknown_logger=logger)
    for now in range(5):
        session.observe("Uncharted Place", 1, now)
    assert not path.exists()
    assert not logger.detector.count


def test_ttl_validation():
    with pytest.raises(ValueError, match="soft TTL"):
        UnknownCaptureConfig(parent_context_soft_ttl_seconds=301)


def test_append_after_partial_record_recovers(tmp_path):
    path = tmp_path / "observations.jsonl"
    path.write_text("{partial", encoding="utf-8")
    matcher = make_matcher()
    session = AutoSession(
        matcher, unknown_logger=UnknownLocationLogger(path, matcher.config.unknown_capture)
    )
    for now in range(3):
        session.observe("Uncharted Place", 0.95, now)
    index = UnknownLocationIndex().load(path)
    assert index.skipped_lines == 1
    assert len(index.groups) == 1


def test_same_label_different_parents_consolidates_separately(tmp_path):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    session = AutoSession(
        matcher, unknown_logger=UnknownLocationLogger(path, matcher.config.unknown_capture)
    )
    for start, label in ((0, "Westfall"), (10, "Duskwood")):
        for now in range(start, start + 3):
            session.observe(label, 1, now)
        for now in range(start + 3, start + 6):
            session.observe("Uncharted Place", 1, now)
    summary = UnknownLocationIndex().load(path).summary()["unknown_locations"]
    assert len(summary) == 2
    assert {r["parent_profile"] for r in summary.values()} == {"westfall", "duskwood"}


def test_saved_discovery_is_not_repeated_after_cooldown_or_restart(tmp_path):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    session = AutoSession(
        matcher, unknown_logger=UnknownLocationLogger(path, matcher.config.unknown_capture)
    )
    for start in (0, 400):
        session.pause()
        for now in range(start, start + 3):
            session.observe("Uncharted Place", 0.95, now)
    original = path.read_bytes()
    assert len(original.splitlines()) == 1
    restarted = AutoSession(
        matcher, unknown_logger=UnknownLocationLogger(path, matcher.config.unknown_capture)
    )
    for now in range(3):
        restarted.observe("  UNCHARTED   PLACE! ", 0.95, now)
    assert path.read_bytes() == original
    for now in range(3, 6):
        restarted.observe("Another Uncharted Place", 0.95, now)
    assert len(path.read_bytes().splitlines()) == 2


def test_failed_write_does_not_mark_discovery_saved(tmp_path, monkeypatch):
    matcher = make_matcher()
    path = tmp_path / "observations.jsonl"
    logger = UnknownLocationLogger(path, matcher.config.unknown_capture)
    session = AutoSession(matcher, unknown_logger=logger)
    original_open = Path.open

    def failing_open(self, *args, **kwargs):
        if self == path and args and args[0] == "a":
            raise OSError("Simulated disk failure")
        return original_open(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_open)
        for now in range(3):
            session.observe("Uncharted Place", 0.95, now)
    assert not logger.seen
    session.observe("Uncharted Place", 0.95, 3)
    assert len(path.read_bytes().splitlines()) == 1
