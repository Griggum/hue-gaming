import random
from dataclasses import dataclass

from .models import LightingConfig, Motion, Profile

# Independent per-light intervals and maximum brightness change per step.
MOTION = {
    Motion.STATIC: (90, 180, 2),
    Motion.SUBTLE: (45, 120, 4),
    Motion.AMBIENT: (20, 90, 7),
    Motion.ACTIVE: (12, 40, 8),
}

EFFECTS = {
    "forest": (20, 90, 6),
    "embers": (3, 15, 8),
    "arcane": (10, 30, 6),
    "snow": (40, 120, 3),
    "haunted": (30, 100, 4),
}


@dataclass(frozen=True)
class Target:
    color: str
    brightness: float
    seconds: float


class AmbientEngine:
    def __init__(
        self, profile: Profile, seed: int | None = None, lighting: LightingConfig | None = None
    ):
        self.profile = profile
        self.lighting = lighting or LightingConfig()
        self.random = random.Random(seed)
        self.current: dict[str, Target] = {}
        self.due: dict[str, float] = {}
        self.base_brightness: dict[str, float] = {}

    def step(self, now: float) -> dict[str, Target]:
        changed = {}
        low, high, drift = EFFECTS.get(self.profile.effect, MOTION[self.profile.motion])
        for channel, light in self.profile.lights.items():
            if channel in self.current and self.lighting.intensity == 0:
                continue
            if channel in self.due and now < self.due[channel]:
                continue
            interval_low, interval_high = light.interval_seconds or (low, high)
            # Warm forest fill stays quieter than the dominant front lights.
            if (
                self.profile.effect == "forest"
                and channel not in ("rectangle_front_left", "rectangle_front_right")
                and not light.interval_seconds
            ):
                interval_low, interval_high = 60, 120
            interval = max(
                3, self.random.uniform(interval_low, interval_high) / self.lighting.speed
            )
            previous = self.current.get(channel)
            minimum, maximum = light.brightness
            midpoint = (minimum + maximum) / 2
            minimum = midpoint + (minimum - midpoint) * self.lighting.intensity
            maximum = midpoint + (maximum - midpoint) * self.lighting.intensity
            if previous:
                minimum = max(
                    minimum, self.base_brightness[channel] - drift * self.lighting.intensity
                )
                maximum = min(
                    maximum, self.base_brightness[channel] + drift * self.lighting.intensity
                )
            brightness = self.random.uniform(minimum, maximum)
            self.base_brightness[channel] = brightness
            palette = light.palette
            # Walk to a neighbouring palette entry instead of jumping across it.
            color = self.random.choice(palette) if previous is None else previous.color
            if (
                previous
                and self.profile.motion != Motion.STATIC
                and self.random.random() < self.lighting.intensity
            ):
                index = palette.index(previous.color)
                color = palette[max(0, min(len(palette) - 1, index + self.random.choice((-1, 1))))]
            target = Target(
                color=color,
                brightness=brightness
                * self.lighting.brightness
                * self.lighting.channel_brightness.get(channel, 1),
                seconds=max(2, interval * 0.75) if previous else self.profile.transition_seconds,
            )
            self.current[channel] = changed[channel] = target
            self.due[channel] = now + max(interval, target.seconds)
        return changed
