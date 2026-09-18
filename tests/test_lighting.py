import re
from pathlib import Path

import pytest

from wow_hue.ambient import EFFECTS, AmbientEngine
from wow_hue.config import load_config
from wow_hue.location_ocr import load_detection
from wow_hue.models import LightingConfig

ROOT = Path(__file__).resolve().parents[1]


def catalog():
    return load_config(ROOT / "config/app.yaml")[1]


def test_every_spec_location_has_a_resolvable_profile():
    spec = (ROOT / "wow-forever-hue-ambient-spec.md").read_text(encoding="utf-8")
    section = spec.split("# 27.")[1].split("# 35.")[0]
    _, matcher = load_detection(ROOT / "config/ocr.yaml", catalog())
    for name in re.findall(r"^## (.+)$", section, re.MULTILINE):
        match = matcher.match(name, 1)
        assert match is not None, name
        assert match.confidence == 1, name


@pytest.mark.parametrize("effect", list(EFFECTS))
def test_effect_bounds_timing_and_independence(effect):
    profile = catalog().profiles["elwynn_forest"].model_copy(update={"effect": effect})
    engine = AmbientEngine(profile, 13)
    for now in range(0, 1800, 2):
        previous = engine.current.copy()
        targets = engine.step(now)
        for channel, target in targets.items():
            light = profile.lights[channel]
            assert target.color in light.palette
            assert light.brightness[0] <= target.brightness <= light.brightness[1]
            assert target.seconds >= 2
            assert engine.due[channel] - now >= 3
            if channel in previous:
                assert abs(previous[channel].brightness - target.brightness) <= EFFECTS[effect][2]
    assert len(set(engine.due.values())) == 5


def test_brightness_and_channel_trim_do_not_change_timing():
    profile = catalog().profiles["duskwood"]
    original = AmbientEngine(profile, 12)
    dimmed = AmbientEngine(
        profile, 12, LightingConfig(brightness=0.5, channel_brightness={"bedside": 0.4})
    )
    for now in range(600):
        baseline, adjusted = original.step(now), dimmed.step(now)
        assert baseline.keys() == adjusted.keys()
        for channel, target in adjusted.items():
            factor = 0.2 if channel == "bedside" else 0.5
            assert target.brightness == pytest.approx(baseline[channel].brightness * factor)
            assert target.color == baseline[channel].color


def test_zero_intensity_sends_initial_midpoints_then_stops():
    profile = catalog().profiles["onyxias_lair"]
    engine = AmbientEngine(profile, 2, LightingConfig(intensity=0))
    targets = engine.step(0)
    for channel, target in targets.items():
        assert target.brightness == sum(profile.lights[channel].brightness) / 2
    assert not engine.step(1000)


def test_speed_and_per_light_interval():
    profile = catalog().profiles["duskwood"].model_copy(deep=True)
    profile.lights["bedside"].interval_seconds = (60, 60)
    engine = AmbientEngine(profile, 1, LightingConfig(speed=2))
    engine.step(0)
    assert engine.due["bedside"] == 30


@pytest.mark.parametrize(
    "values",
    [
        {"brightness": 2},
        {"intensity": -1},
        {"speed": 0},
        {"speed": float("nan")},
        {"channel_brightness": {"missing": 1}},
        {"channel_brightness": {"bedside": float("inf")}},
    ],
)
def test_invalid_tuning_rejected(values):
    with pytest.raises(ValueError):
        LightingConfig(**values)


def test_all_profiles_survive_simulation():
    for profile in catalog().profiles.values():
        engine = AmbientEngine(profile, 7)
        for now in range(0, 600, 10):
            for channel, target in engine.step(now).items():
                assert target.color in profile.lights[channel].palette
                assert 0 <= target.brightness <= 100
