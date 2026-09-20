from pathlib import Path

import pytest

from wow_hue.auto import AutoSession
from wow_hue.config import load_config
from wow_hue.location_ocr import Calibration, Detector, Matcher, OCRConfig, load_detection

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def matcher():
    _, catalog = load_config(ROOT / "config/app.yaml")
    return load_detection(ROOT / "config/ocr.yaml", catalog)[1]


def test_subzones_resolve_and_preserve_raw(matcher):
    match = matcher.match(" GOLDShire! ", 0.95)
    assert match.raw_location == " GOLDShire! "
    assert match.matched == "Goldshire"
    assert match.profile == "elwynn_forest"
    assert match.resolved_location == "Elwynn Forest"
    assert matcher.match("The Slaughtered Lamb", 0.94).profile == "stormwind"
    assert matcher.match("The Deadmines", 0.99).profile == "deadmines"
    assert matcher.match("Alterac Valley", 0.99).profile == "alterac_valley"


def test_three_consecutive_reads_and_ocr_typo(matcher):
    detector = Detector(matcher)
    assert not detector.observe("Duskwood", 0.96)[1]
    assert not detector.observe("Duskwo0d", 0.89)[1]
    assert detector.observe("Duskwood", 0.97)[1]
    assert not detector.observe("Duskwood", 0.97)[1]


@pytest.mark.parametrize(
    "text,confidence", [("", 1), ("?", 1), ("Goldshire", 0.2), ("Completely unknown place", 0.99)]
)
def test_unknown_breaks_streak_but_holds_confirmed(matcher, text, confidence):
    detector = Detector(matcher)
    for _ in range(3):
        detector.observe("Duskwood", 0.95)
    detector.observe("Goldshire", 0.95)
    detector.observe(text, confidence)
    assert detector.confirmed == "duskwood"
    assert detector.count == 0
    assert not detector.observe("Goldshire", 0.95)[1]
    assert not detector.observe("Goldshire", 0.95)[1]
    assert detector.observe("Goldshire", 0.95)[1]


def test_changing_subzones_does_not_restart_engine(matcher):
    session = AutoSession(matcher, seed=42)
    for t in range(3):
        session.observe("Goldshire", 0.95, t)
    engine = session.engine
    for t in range(3, 6):
        assert not session.observe("Northshire Valley", 0.95, t)[1]
    assert session.engine is engine
    session.observe("unknown label", 0.95, 100)
    assert session.engine is engine


def test_changed_parent_clears_stale_hue_targets(matcher):
    class Controller:
        def __init__(self):
            self.pending = {"stale": None}

        def submit(self, targets):
            self.pending.update(targets)

        def flush(self, now):
            return False

    controller = Controller()
    session = AutoSession(matcher, controller)
    for t in range(3):
        session.observe("Goldshire", 0.95, t)
    assert "stale" not in controller.pending
    assert len(controller.pending) == 5


def test_ambiguous_fuzzy_matches_rejected(matcher):
    matcher.add("East Tower", "stormwind")
    matcher.add("West Tower", "duskwood")
    assert matcher.match("est tower", 1) is None


def test_alias_validation(matcher):
    with pytest.raises(ValueError, match="Unknown parent"):
        Matcher(
            matcher.catalog, {"location_aliases": {"Unknown": {"parent": "missing"}}}, OCRConfig()
        )
    with pytest.raises(ValueError, match="Ambiguous"):
        matcher.add("Goldshire", "duskwood")


@pytest.mark.parametrize(
    "text,profile",
    [
        ("Stranglethorn...", "stranglethorn_vale"),
        ("Strangleth0rn…", "stranglethorn_vale"),
        ("The Slaughter", "stormwind"),
        ("Northshire Val", "elwynn_forest"),
    ],
)
def test_clipped_labels(matcher, text, profile):
    match = matcher.match(text, 0.95)
    assert match is not None
    assert match.profile == profile


@pytest.mark.parametrize("text", ["Scarlet Monastery", "The", "Strang"])
def test_short_or_ambiguous_prefix_rejected(matcher, text):
    assert matcher.match(text, 0.95) is None


def test_prefix_parent_ambiguity_beats_length_advantage(matcher):
    matcher.add("Crystal Valley", "duskwood")
    matcher.add("Crystal Valley Northern Outpost", "stormwind")
    assert matcher.match("Crystal Valle", 0.95) is None


def test_prefix_aliases_with_same_parent_are_safe(matcher):
    matcher.add("Crystal Valley", "duskwood")
    matcher.add("Crystal Vale", "duskwood")
    assert matcher.match("Crystal Va", 0.95).profile == "duskwood"


def test_prefix_still_requires_confidence_and_three_reads(matcher):
    detector = Detector(matcher)
    assert detector.observe("Stranglethorn...", 0.2) == (None, False)
    assert not detector.observe("Stranglethorn...", 0.95)[1]
    assert not detector.observe("Stranglethorn...", 0.95)[1]
    assert detector.observe("Stranglethorn...", 0.95)[1]


def test_roi_validation():
    roi = Calibration(left=100, top=20, width=200, height=30, client_width=1920, client_height=1080)
    assert roi.rectangle(1920, 1080) == (100, 20, 200, 30)
    with pytest.raises(ValueError, match="recalibrate"):
        roi.rectangle(2560, 1440)
    roi.left = 1900
    with pytest.raises(ValueError, match="outside"):
        roi.rectangle(1920, 1080)


def test_local_ocr_generated_label():
    # Synthetic smoke fixture, not a claim of accuracy on the WoW font.
    from PIL import Image, ImageDraw, ImageFont

    from wow_hue.screen import LocalOCR

    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if not font_path.exists():
        pytest.skip("Windows font fixture unavailable")
    image = Image.new("RGB", (320, 40), "black")
    ImageDraw.Draw(image).text(
        (8, 5), "Goldshire", font=ImageFont.truetype(str(font_path), 24), fill="white"
    )
    raw, score = LocalOCR().read(image)
    assert raw == "Goldshire"
    assert score > 0.8
