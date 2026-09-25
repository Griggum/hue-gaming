"""Authenticate API requests before parsing or buffering their bodies."""

import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from hue_core.sync import MAX_BYTES


class APIGuard:
    def __init__(self, app, token: str, public_origin: str | None = None):
        self.app = app
        self.expected = f"Bearer {token}".encode()
        self.public_origin = public_origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        supplied = headers.get("authorization", "").encode()
        if not secrets.compare_digest(supplied, self.expected):
            return await JSONResponse({"detail": "Enter the portal access token"}, 401)(
                scope, receive, send
            )
        origin = headers.get("origin")
        expected_origin = self.public_origin or f"{scope['scheme']}://{headers.get('host', '')}"
        if origin and origin != expected_origin:
            return await JSONResponse({"detail": "Cross-origin requests are disabled"}, 403)(
                scope, receive, send
            )
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if len(body) > MAX_BYTES:
                return await JSONResponse({"detail": "Request exceeds 8 MiB limit"}, 413)(
                    scope, receive, send
                )
            if not event.get("more_body", False):
                break

        async def buffered_receive():
            nonlocal body
            if body is not None:
                result, body = bytes(body), None
                return {"type": "http.request", "body": result, "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)
