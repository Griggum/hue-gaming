import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field

from hue_core.catalog import Library, atomic_write
from hue_core.config import load_mapping
from hue_core.hue import Bridge, BridgeError
from hue_core.models import BridgeConfig, LightingConfig, Model

from .control import Player
from .security import APIGuard
from .store import ConflictError, Store


class PlayRequest(Model):
    scene: str
    ambient: bool = False
    lighting: LightingConfig = Field(default_factory=LightingConfig)


def create_app(*, data_dir=None, seed=None, token=None, player=None, public_origin=None):
    data_dir = Path(data_dir or os.getenv("HUE_DATA_DIR", "data"))
    seed = Path(seed or os.getenv("HUE_SEED_FILE", "config/library.seed.json"))
    token = token or os.getenv("HUE_PORTAL_TOKEN", "")
    if len(token) < 24:
        raise ValueError("HUE_PORTAL_TOKEN must contain at least 24 characters")
    public_origin = public_origin or os.getenv("HUE_PUBLIC_ORIGIN")
    if public_origin:
        parsed = urlsplit(public_origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("HUE_PUBLIC_ORIGIN must be an HTTPS origin without a trailing slash")
    store = Store(data_dir / "library.json", seed)

    def bridge_factory():
        host, key = os.getenv("HUE_BRIDGE_IP"), os.getenv("HUE_USERNAME")
        if not host or not key:
            raise ValueError("Set HUE_BRIDGE_IP and HUE_USERNAME on the server")
        return Bridge(
            host,
            key,
            BridgeConfig(ca_file=os.getenv("HUE_CA_FILE")),
            insecure=os.getenv("HUE_INSECURE", "false").lower() == "true",
        )

    @asynccontextmanager
    async def lifespan(app):
        app.state.player = player or Player(
            bridge_factory, lambda: load_mapping(data_dir / "lights.yaml")
        )
        try:
            yield
        finally:
            app.state.player.close()

    app = FastAPI(
        title="Hue profile portal",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store

    app.add_middleware(APIGuard, token=token, public_origin=public_origin)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Do not echo submitted fields or accidental secrets in validation responses.
        return JSONResponse(status_code=422, content={"detail": "Invalid request fields or values"})

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(ConflictError)
    async def conflict(request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        store.read()
        return {"status": "ready"}

    @app.get("/")
    def index():
        return FileResponse(Path(__file__).parent / "static/index.html")

    @app.get("/assets/{name}")
    def asset(name: str):
        if name not in {"app.js", "style.css"}:
            raise HTTPException(404)
        return FileResponse(Path(__file__).parent / "static" / name)

    @app.get("/api/library")
    def library():
        return store.read()

    @app.put("/api/library")
    def save(library: Library):
        return store.save(library)

    @app.get("/api/status")
    def status():
        return app.state.player.status()

    @app.get("/api/lights")
    def lights():
        try:
            bridge = bridge_factory()
            try:
                return {
                    "resources": bridge.lights(),
                    "mapping": load_mapping(data_dir / "lights.yaml", complete=False),
                }
            finally:
                bridge.close()
        except (BridgeError, ValueError, OSError):
            raise HTTPException(
                503, "Unable to read bridge lights; check server configuration"
            ) from None

    @app.put("/api/mapping")
    def mapping(body: dict[str, str]):
        from hue_core.config import validate_mapping
        from hue_core.hue import Controller

        try:
            body = validate_mapping(body)
            bridge = bridge_factory()
            try:
                Controller(bridge, body, bridge.lights())
            finally:
                bridge.close()
            # Stop the old mapping before persisting a new set of physical lights.
            with app.state.player.lock:
                app.state.player._stop()
                atomic_write(data_dir / "lights.yaml", yaml.safe_dump(body))
        except (ValueError, TypeError):
            raise HTTPException(
                422, "Map all five channels to distinct dimmable bridge lights"
            ) from None
        except (BridgeError, OSError):
            raise HTTPException(503, "Unable to validate or save light mapping") from None
        return {"mapping": body}

    @app.post("/api/play")
    def play(body: PlayRequest):
        library = store.read()
        if body.scene not in library.scenes:
            raise HTTPException(404, "Unknown scene")
        try:
            app.state.player.play(
                body.scene, library.scenes[body.scene], body.lighting, body.ambient
            )
        except (BridgeError, ValueError, OSError):
            raise HTTPException(
                503, "Unable to apply scene; check bridge and light mapping"
            ) from None
        return app.state.player.status()

    @app.post("/api/stop")
    def stop():
        app.state.player.stop()
        return app.state.player.status()

    return app


def main():
    import uvicorn

    uvicorn.run(
        "hue_portal.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8080,
        workers=1,
        proxy_headers=False,
    )
