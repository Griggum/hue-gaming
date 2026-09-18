import copy
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from wow_hue.ambient import MOTION, AmbientEngine, Target
from wow_hue.config import Catalog, credentials, load_config, load_mapping, read_yaml
from wow_hue.hue import AuthenticationError, Bridge, BridgeError, Controller, clip_to_gamut, payload
from wow_hue.main import execute, parser
from wow_hue.models import CHANNELS, BridgeConfig, Motion

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def raw():
    return read_yaml(ROOT / "config/profiles.yaml")


def test_catalog_alias_and_map_id(raw):
    raw["locations"]["duskwood"]["map_ids"] = [1234]
    catalog = Catalog(raw)
    assert catalog.resolve(" ELWYNN   forest ") == "elwynn_forest"
    assert catalog.resolve("Onyxia’s Lair") == "onyxias_lair"
    assert catalog.resolve("unknown", 1234) == "duskwood"
    assert catalog.resolve("unknown") is None


@pytest.mark.parametrize(
    "change", ["color", "brightness", "channel", "alias", "transition", "map_id"]
)
def test_invalid_profiles(raw, change):
    profile = raw["locations"]["duskwood"]
    light = profile["lights"]["bedside"]
    if change == "color":
        light["palette"] = ["red"]
    elif change == "brightness":
        light["brightness"] = [25, 10]
    elif change == "channel":
        del profile["lights"]["bedside"]
    elif change == "alias":
        profile["names"] = ["Elwynn Forest"]
    elif change == "transition":
        profile["transition_seconds"] = 0
    else:
        profile["map_ids"] = [1]
        raw["locations"]["westfall"]["map_ids"] = [1]
    with pytest.raises(ValueError):
        Catalog(raw)


def test_duplicate_yaml_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("locations: {}\nlocations: {}\n")
    with pytest.raises(ValueError, match="Duplicate"):
        read_yaml(path)


@pytest.mark.parametrize("mode", list(Motion))
def test_motion_deterministic_independent_and_bounded(raw, mode):
    profile = (
        Catalog(raw).profiles["duskwood"].model_copy(update={"motion": mode, "effect": "default"})
    )
    first, second = AmbientEngine(profile, 17), AmbientEngine(profile, 17)
    for now in range(1800):
        previous = copy.copy(first.current)
        targets = first.step(now)
        assert targets == second.step(now)
        for channel, target in targets.items():
            spec = profile.lights[channel]
            assert target.color in spec.palette
            assert spec.brightness[0] <= target.brightness <= spec.brightness[1]
            if channel in previous:
                assert abs(previous[channel].brightness - target.brightness) <= MOTION[mode][2]
            else:
                assert target.seconds == profile.transition_seconds
    assert len(set(first.due.values())) == 5


def test_credentials_use_hue_username_and_preserve_literals(tmp_path, monkeypatch):
    monkeypatch.delenv("HUE_USERNAME", raising=False)
    monkeypatch.setenv("USERNAME", "windows-user")
    path = tmp_path / ".env"
    path.write_text("HUE_USERNAME=test-${USERNAME}\nAPI_TOKEN=unused\n")
    assert credentials(path)[0] == "test-${USERNAME}"
    monkeypatch.setenv("HUE_USERNAME", "override")
    assert credentials(path)[0] == "override"


def test_mapping_uniqueness_and_completeness(tmp_path):
    path = tmp_path / "lights.yaml"
    with pytest.raises(ValueError, match="five"):
        load_mapping(path)
    path.write_text(f"{CHANNELS[0]}: {UUID(int=1)}\n{CHANNELS[1]}: {UUID(int=1)}\n")
    with pytest.raises(ValueError, match="different"):
        load_mapping(path, complete=False)


def test_hue_transport_and_payload():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [], "errors": []})

    bridge = Bridge(
        "192.168.1.2",
        "test-key",
        BridgeConfig(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    try:
        bridge.lights()
        body = payload(Target("#4F8A3C", 40, 4), {"color": {}})
        bridge.update(str(UUID(int=1)), body)
    finally:
        bridge.close()
    assert seen[0].url.path == "/clip/v2/resource/light"
    assert seen[0].headers["hue-application-key"] == "test-key"
    assert "test-key" not in str(seen[0].url)
    assert json.loads(seen[1].content)["dynamics"]["duration"] == 4000
    assert "color" not in payload(Target("#FFFFFF", 20, 4), {})
    assert not payload(Target("#000000", 0, 4), {})["on"]["on"]


def test_gamut_clipping():
    gamut = {
        "red": {"x": 0.7, "y": 0.3},
        "green": {"x": 0.2, "y": 0.7},
        "blue": {"x": 0.1, "y": 0.1},
    }
    assert clip_to_gamut((0.3, 0.3), gamut) == (0.3, 0.3)
    point = clip_to_gamut((1, 0), gamut)
    assert point == pytest.approx((0.7, 0.3))


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, {}, AuthenticationError),
        (200, {"errors": [{"description": "no"}], "data": []}, BridgeError),
        (503, {}, BridgeError),
        (200, [], BridgeError),
    ],
)
def test_bridge_failures(status, body, error):
    bridge = Bridge(
        "192.168.1.2",
        "secret",
        BridgeConfig(),
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)),
    )
    try:
        with pytest.raises(error) as raised:
            bridge.lights()
        assert "secret" not in str(raised.value)
    finally:
        bridge.close()


def test_retry_coalesces_and_restores_latest_state():
    class FakeBridge:
        fail = True

        def __init__(self):
            self.sent = []

        def update(self, resource_id, body):
            if self.fail:
                raise BridgeError("offline")
            self.sent.append(body)

    bridge = FakeBridge()
    controller = Controller(bridge, {"bedside": "1"}, [{"id": "1", "dimming": {}, "color": {}}])
    controller.submit({"bedside": Target("#FFFFFF", 20, 4)})
    assert not controller.flush(0)
    assert controller.retry_at == 1
    assert not controller.flush(1)
    assert controller.retry_at == 3
    controller.submit({"bedside": Target("#FFFFFF", 35, 4)})
    bridge.fail = False
    assert not controller.flush(2)
    assert controller.flush(3)
    assert bridge.sent[0]["dimming"]["brightness"] == 35
    assert not controller.pending
    assert controller.failures == 0


def test_dry_run_needs_no_credentials(capsys):
    args = parser().parse_args(
        [
            "--config",
            str(ROOT / "config/app.yaml"),
            "profile",
            "duskwood",
            "--dry-run",
            "--seed",
            "1",
        ]
    )
    assert execute(args) == 0
    assert set(json.loads(capsys.readouterr().out)) == set(CHANNELS)


def test_config_loads():
    _, catalog = load_config(ROOT / "config/app.yaml")
    assert len(catalog.profiles) >= 98
