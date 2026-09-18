from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHANNELS = (
    "rectangle_front_left",
    "rectangle_front_right",
    "rectangle_rear_left",
    "rectangle_rear_right",
    "bedside",
)
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Seconds = Annotated[float, Field(gt=0, le=600, allow_inf_nan=False)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Motion(StrEnum):
    STATIC = "static"
    SUBTLE = "subtle"
    AMBIENT = "ambient"
    ACTIVE = "active"


class LightProfile(Model):
    interval_seconds: tuple[Seconds, Seconds] | None = None
    palette: list[Color] = Field(min_length=1)
    brightness: tuple[Percent, Percent]

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.interval_seconds and self.interval_seconds[0] > self.interval_seconds[1]:
            raise ValueError("interval minimum exceeds maximum")
        if self.brightness[0] > self.brightness[1]:
            raise ValueError("brightness minimum exceeds maximum")
        return self


class Profile(Model):
    effect: Literal["default", "forest", "embers", "arcane", "snow", "haunted"] = "default"
    names: list[str] = Field(min_length=1)
    map_ids: list[int] = Field(default_factory=list)
    type: Literal["zone", "city", "dungeon", "raid", "battleground", "neutral"] = "zone"
    motion: Motion = Motion.AMBIENT
    transition_seconds: Seconds = 4
    lights: dict[str, LightProfile]

    @model_validator(mode="after")
    def validate_channels(self):
        if set(self.lights) != set(CHANNELS):
            raise ValueError(f"lights must contain exactly: {', '.join(CHANNELS)}")
        if any(not name.strip() for name in self.names):
            raise ValueError("location names must not be blank")
        return self


class LocationState(Model):
    canonical_id: str | None = None
    display_name: str | None = None
    map_id: int | None = None
    instance_id: int | None = None
    instance_type: str = "unknown"
    difficulty_id: int | None = None
    source: str = "manual"
    confidence: float = Field(default=1, ge=0, le=1)


class BridgeConfig(Model):
    host: str | None = None
    ca_file: str | None = None
    request_interval_seconds: float = Field(default=0.25, ge=0.1, le=10)
    timeout_seconds: float = Field(default=5, gt=0, le=60)
    max_retry_seconds: float = Field(default=30, ge=1, le=300)


class AppConfig(Model):
    lighting: "LightingConfig" = Field(default_factory=lambda: LightingConfig())
    ocr: str = "ocr.yaml"
    profiles: str = "profiles.yaml"
    lights: str = "lights.yaml"
    env_file: str = "../.env"
    log_file: str = "../logs/wow-hue.log"
    bridge: BridgeConfig = Field(default_factory=BridgeConfig)


class LightingConfig(Model):
    brightness: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    intensity: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    speed: float = Field(default=1, ge=0.25, le=2, allow_inf_nan=False)
    channel_brightness: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_channels(self):
        import math

        if set(self.channel_brightness) - set(CHANNELS):
            raise ValueError("Unknown channel in channel_brightness")
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in self.channel_brightness.values()):
            raise ValueError("Channel brightness must be between 0 and 1")
        return self
