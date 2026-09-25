from typing import Literal

from pydantic import Field, model_validator

from hue_core.models import (
    CHANNELS,
    BridgeConfig,
    LightingConfig,
    LightProfile,
    Model,
    Motion,
    Scene,
    Seconds,
)

__all__ = [
    "CHANNELS",
    "AppConfig",
    "BridgeConfig",
    "LightProfile",
    "LightingConfig",
    "LocationState",
    "Model",
    "Motion",
    "Profile",
    "Seconds",
]


class Profile(Scene):
    name: str = "WoW profile"
    names: list[str] = Field(min_length=1)
    map_ids: list[int] = Field(default_factory=list)
    type: Literal["zone", "city", "dungeon", "raid", "battleground", "neutral"] = "zone"

    @model_validator(mode="after")
    def validate_location_names(self):
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


class AppConfig(Model):
    lighting: "LightingConfig" = Field(default_factory=lambda: LightingConfig())
    ocr: str = "ocr.yaml"
    profiles: str = "profiles.yaml"
    profile_cache: str | None = None
    lights: str = "lights.yaml"
    env_file: str = "../.env"
    log_file: str = "../logs/wow-hue.log"
    bridge: BridgeConfig = Field(default_factory=BridgeConfig)
