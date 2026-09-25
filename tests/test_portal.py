import copy
import shutil
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from hue_core.catalog import Library
from hue_core.models import CHANNELS, LightingConfig
from hue_core.sync import pull
from hue_portal.app import create_app
from hue_portal.control import Player
from hue_portal.store import ConflictError, Store
from wow_hue.config import load_config, read_yaml
from wow_hue.library import import_wow, wow_catalog

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "config/library.seed.json"
TOKEN = "test-portal-token-at-least-24-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def library():
    return Library.model_validate_json(SEED.read_text())


def test_migration_preserves_wow_behavior_and_cross_game_names(library):
    old = import_wow(read_yaml(ROOT / "config/profiles.yaml"))
    assert len(old.scenes) == 98
    catalog = wow_catalog(library)
    assert catalog.resolve("Elwynn Forest") == "elwynn_forest"
    assert catalog.profiles["duskwood"].lights == old.scenes["wow_duskwood"].lights
    assert library.resolve("valheim", "Black Forest") == "valheim_black_forest"
    raw = library.model_dump()
    raw["games"]["other"] = copy.deepcopy(raw["games"]["wow"])
    Library.model_validate(raw)  # The same event names are legal in different games.
    raw["games"]["other"]["events"]["new"] = {"names": ["Elwynn Forest"], "scene": "wow_duskwood"}
    with pytest.raises(ValueError, match="ambiguous"):
        Library.model_validate(raw)


@pytest.mark.parametrize("mutation", ["dangling", "schema", "color", "channel", "nan"])
def test_invalid_library_rejected(library, mutation):
    raw = library.model_dump()
    scene = raw["scenes"]["wow_duskwood"]
    if mutation == "dangling":
        del raw["scenes"]["wow_duskwood"]
    elif mutation == "schema":
        raw["schema_version"] = 99
    elif mutation == "color":
        scene["lights"]["bedside"]["palette"] = ["red"]
    elif mutation == "channel":
        del scene["lights"]["bedside"]
    else:
        scene["transition_seconds"] = float("nan")
    with pytest.raises(ValueError):
        Library.model_validate(raw)


def test_store_revision_restart_and_corruption(tmp_path, library):
    path = tmp_path / "library.json"
    store = Store(path, SEED)
    library.scenes["wow_duskwood"].name = "Custom forest"
    saved = store.save(library)
    assert saved.revision == 2
    assert Store(path, SEED).read().scenes["wow_duskwood"].name == "Custom forest"
    with pytest.raises(ConflictError):
        store.save(library)
    path.write_text("broken")
    with pytest.raises(ValueError):
        Store(path, SEED)
    assert path.read_text() == "broken"


def test_sync_updates_and_retains_last_good_on_failure(tmp_path, library):
    cache = tmp_path / "cache.json"
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=library.model_dump(mode="json"))

    transport = httpx.MockTransport(handler)
    assert pull("http://pi:8080", TOKEN, cache, transport=transport)
    assert not pull("http://pi:8080", TOKEN, cache, transport=transport)
    assert requests[0].headers["authorization"] == AUTH["Authorization"]
    assert requests[0].url.path == "/api/library"
    before = cache.read_bytes()
    for response in [
        httpx.Response(401),
        httpx.Response(500),
        httpx.Response(200, json={"schema_version": 99}),
        httpx.Response(302, headers={"Location": "http://other"}),
        httpx.Response(200, content=b"truncated"),
    ]:
        with pytest.raises((httpx.HTTPError, ValueError)):
            pull(
                "http://pi:8080",
                TOKEN,
                cache,
                transport=httpx.MockTransport(lambda _, result=response: result),
            )
        assert cache.read_bytes() == before

    def offline(request):
        raise httpx.ConnectError("offline")

    with pytest.raises(httpx.ConnectError):
        pull("http://pi:8080", TOKEN, cache, transport=httpx.MockTransport(offline))
    assert cache.read_bytes() == before


def test_wow_uses_local_cache_without_network_and_falls_back(tmp_path, library, monkeypatch):
    config_dir = tmp_path / "config"
    shutil.copytree(
        ROOT / "config",
        config_dir,
        ignore=shutil.ignore_patterns("lights.yaml", "ocr.local.yaml", "*.cache.json"),
    )
    cache = config_dir / "profiles.cache.json"
    library.scenes["wow_duskwood"].lights["bedside"].palette = ["#123456"]
    cache.write_text(library.model_dump_json())

    def no_network(*args, **kwargs):
        pytest.fail("Loading a game profile must never contact the Pi")

    monkeypatch.setattr(httpx.Client, "request", no_network)
    _, catalog = load_config(config_dir / "app.yaml")
    assert catalog.profiles["duskwood"].lights["bedside"].palette == ["#123456"]
    cache.write_text("damaged")
    _, fallback = load_config(config_dir / "app.yaml")
    assert fallback.profiles["duskwood"].lights["bedside"].palette != ["#123456"]
    # An incompatible WoW registry also falls back without breaking OCR startup.
    library.games["wow"].events.pop("duskwood")
    cache.write_text(library.model_dump_json())
    _, fallback = load_config(config_dir / "app.yaml")
    assert "duskwood" in fallback.profiles


class FakePlayer:
    def __init__(self):
        self.played = None
        self.closed = False

    def play(self, scene_id, scene, lighting, ambient):
        self.played = (scene_id, scene, lighting, ambient)

    def status(self):
        return {"scene": self.played[0] if self.played else None}

    def stop(self):
        self.played = None

    def close(self):
        self.closed = True


def test_api_auth_edits_conflicts_play_and_stop(tmp_path, library):
    player = FakePlayer()
    app = create_app(data_dir=tmp_path, seed=SEED, token=TOKEN, player=player)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/library").status_code == 401
        raw = client.get("/api/library", headers=AUTH).json()
        assert "HUE_USERNAME" not in str(raw)
        raw["scenes"]["wow_duskwood"]["name"] = "Edited"
        saved = client.put("/api/library", headers=AUTH, json=raw)
        assert saved.status_code == 200
        assert saved.json()["revision"] == 2
        assert client.put("/api/library", headers=AUTH, json=raw).status_code == 409
        invalid = saved.json()
        del invalid["scenes"]["wow_duskwood"]
        assert client.put("/api/library", headers=AUTH, json=invalid).status_code == 422
        assert client.post("/api/play", json={"scene": "wow_duskwood"}).status_code == 401
        assert (
            client.post(
                "/api/play", headers=AUTH, json={"scene": "wow_duskwood", "ambient": True}
            ).status_code
            == 200
        )
        assert player.played[0] == "wow_duskwood"
        assert player.played[1].name == "Edited"
        assert player.played[3]
        assert client.post("/api/play", headers=AUTH, json={"scene": "absent"}).status_code == 404
        assert (
            client.post("/api/stop", headers={**AUTH, "Origin": "http://evil"}).status_code == 403
        )
        assert player.played
        assert client.post("/api/stop", headers=AUTH).status_code == 200
        assert player.played is None
    assert player.closed
    assert Store(tmp_path / "library.json", SEED).read().revision == 2


def test_player_direct_hue_delivery_and_stop(library):
    mapping = {c: str(UUID(int=i + 1)) for i, c in enumerate(CHANNELS)}

    class FakeBridge:
        def __init__(self):
            self.updates = []
            self.closed = False

        def lights(self):
            return [{"id": v, "dimming": {}} for v in mapping.values()]

        def update(self, resource_id, body):
            self.updates.append((resource_id, body))

        def close(self):
            self.closed = True

    bridges = []

    def factory():
        bridge = FakeBridge()
        bridges.append(bridge)
        return bridge

    player = Player(factory, lambda: mapping)
    try:
        player.play("first", library.scenes["wow_duskwood"], LightingConfig(), True)
        assert len(bridges[0].updates) == 5
        assert player.status()["ambient"]
        player.play("second", library.scenes["valheim_meadows"], LightingConfig(), False)
        assert bridges[0].closed and bridges[1].closed
        assert len(bridges[1].updates) == 5
        assert player.status()["scene"] == "second"
        assert not player.status()["ambient"]
        player.stop()
        assert player.status()["scene"] is None
    finally:
        player.close()
    assert not player.thread.is_alive()


def test_api_mapping_validation_and_bridge_failure(tmp_path, monkeypatch):
    mapping = {c: str(UUID(int=i + 1)) for i, c in enumerate(CHANNELS)}

    class FakeBridge:
        def __init__(self, *args, **kwargs):
            pass

        def lights(self):
            return [{"id": v, "dimming": {}} for v in mapping.values()]

        def close(self):
            pass

    monkeypatch.setenv("HUE_BRIDGE_IP", "192.168.1.2")
    monkeypatch.setenv("HUE_USERNAME", "test-key")
    monkeypatch.setattr("hue_portal.app.Bridge", FakeBridge)
    app = create_app(data_dir=tmp_path, seed=SEED, token=TOKEN)
    with TestClient(app) as client:
        assert client.put("/api/mapping", json=mapping).status_code == 401
        assert client.put("/api/mapping", headers=AUTH, json={}).status_code == 422
        duplicate = dict.fromkeys(CHANNELS, str(UUID(int=1)))
        assert client.put("/api/mapping", headers=AUTH, json=duplicate).status_code == 422
        assert not (tmp_path / "lights.yaml").exists()
        assert client.put("/api/mapping", headers=AUTH, json=mapping).status_code == 200
        assert read_yaml(tmp_path / "lights.yaml") == mapping
        data = client.get("/api/lights", headers=AUTH).json()
        assert data["mapping"] == mapping
        monkeypatch.delenv("HUE_USERNAME")
        assert (
            client.post("/api/play", headers=AUTH, json={"scene": "wow_duskwood"}).status_code
            == 503
        )
        assert client.get("/api/status", headers=AUTH).json()["error"]
        assert client.get("/api/library", headers=AUTH).status_code == 200


def test_api_security_boundary(tmp_path, monkeypatch):
    # Test the streaming limit with a small ceiling, including chunked bodies.
    monkeypatch.setattr("hue_portal.security.MAX_BYTES", 128)
    app = create_app(
        data_dir=tmp_path,
        seed=SEED,
        token=TOKEN,
        player=FakePlayer(),
        public_origin="https://hue.home.arpa",
    )
    with TestClient(app) as client:
        for path in ["/api/library", "/api/play", "/api/mapping"]:
            # Authentication happens before JSON validation or size checks.
            assert client.put(path, content="{" * 200).status_code == 401
        too_large = client.put("/api/library", headers=AUTH, content=iter([b"{" * 100, b"x" * 100]))
        assert too_large.status_code == 413
        response = client.post(
            "/api/play", headers=AUTH, json={"scene": "x", "secret": "do-not-echo"}
        )
        assert response.status_code == 422
        assert "do-not-echo" not in response.text
        good_origin = {**AUTH, "Origin": "https://hue.home.arpa"}
        assert client.post("/api/stop", headers=good_origin).status_code == 200
        wrong_origin = {**AUTH, "Origin": "http://hue.home.arpa"}
        assert client.post("/api/stop", headers=wrong_origin).status_code == 403
        for path in ["/.env", "/data/library.json", "/data/lights.yaml", "/docs", "/openapi.json"]:
            assert client.get(path).status_code == 404
        response = client.get("/")
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_public_origin_requires_https(tmp_path):
    with pytest.raises(ValueError, match="HTTPS origin"):
        create_app(data_dir=tmp_path, seed=SEED, token=TOKEN, public_origin="http://hue.home.arpa")


def test_portal_passes_bridge_tls_configuration(tmp_path, monkeypatch):
    captured = []

    class FakeBridge:
        def __init__(self, host, key, config, *, insecure):
            captured.append((host, key, config, insecure))

        def lights(self):
            return []

        def close(self):
            pass

    monkeypatch.setenv("HUE_BRIDGE_IP", "192.168.10.128")
    monkeypatch.setenv("HUE_USERNAME", "test-bridge-key")
    monkeypatch.setenv("HUE_CA_FILE", "/etc/hue-tls/hue-ca.pem")
    monkeypatch.setenv("HUE_BRIDGE_ID", "001788fffe123abc")
    monkeypatch.setenv("HUE_INSECURE", "false")
    monkeypatch.setattr("hue_portal.app.Bridge", FakeBridge)
    with TestClient(create_app(data_dir=tmp_path, seed=SEED, token=TOKEN)) as client:
        assert client.get("/api/lights", headers=AUTH).status_code == 200
    host, key, config, insecure = captured[0]
    assert host == "192.168.10.128"
    assert key == "test-bridge-key"
    assert config.ca_file == "/etc/hue-tls/hue-ca.pem"
    assert config.bridge_id == "001788fffe123abc"
    assert insecure is False
