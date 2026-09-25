"""Hue v2 REST transport; credentials never appear in URLs or log messages."""

import ipaddress
import logging
import ssl
import time
from uuid import UUID

import httpx

from .ambient import Target
from .models import BridgeConfig

log = logging.getLogger(__name__)


class BridgeError(Exception):
    pass


class AuthenticationError(BridgeError):
    pass


def rgb_to_xy(color: str) -> tuple[float, float]:
    rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    x = r * 0.664511 + g * 0.154324 + b * 0.162028
    y = r * 0.283881 + g * 0.668433 + b * 0.047685
    z = r * 0.000088 + g * 0.072310 + b * 0.986039
    total = x + y + z
    return (x / total, y / total) if total else (0.3127, 0.3290)


def clip_to_gamut(xy, gamut):
    if not gamut:
        return xy
    vertices = [(gamut[name]["x"], gamut[name]["y"]) for name in ("red", "green", "blue")]

    def cross(a, b, p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    signs = [cross(a, b, xy) for a, b in edges]
    if all(s >= 0 for s in signs) or all(s <= 0 for s in signs):
        return xy
    candidates = []
    for a, b in edges:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = dx * dx + dy * dy
        t = max(0, min(1, ((xy[0] - a[0]) * dx + (xy[1] - a[1]) * dy) / length)) if length else 0
        candidates.append((a[0] + t * dx, a[1] + t * dy))
    return min(candidates, key=lambda p: (p[0] - xy[0]) ** 2 + (p[1] - xy[1]) ** 2)


def payload(target: Target, resource: dict) -> dict:
    body = {
        "on": {"on": target.brightness > 0},
        "dimming": {"brightness": max(0.1, target.brightness)},
        "dynamics": {"duration": round(target.seconds * 1000)},
    }
    if "color" in resource:
        x, y = clip_to_gamut(rgb_to_xy(target.color), resource["color"].get("gamut"))
        body["color"] = {"xy": {"x": x, "y": y}}
    return body


def discover() -> list[dict]:
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get("https://discovery.meethue.com")
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise TypeError("Invalid discovery response")
            return [{"id": item["id"], "ip": item["internalipaddress"]} for item in result]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise BridgeError("Bridge discovery failed; set HUE_BRIDGE_IP manually") from error


class Bridge:
    def __init__(
        self,
        host: str,
        key: str,
        config: BridgeConfig,
        *,
        insecure=False,
        transport=None,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        address = ipaddress.ip_address(host)
        if (
            not address.is_private
            or address.is_loopback
            or address.is_unspecified
            or address.is_multicast
        ):
            raise ValueError("Bridge address must be a private LAN IP")
        host = f"[{address}]" if address.version == 6 else str(address)
        verification = False if insecure else ssl.create_default_context(cafile=config.ca_file)
        self.client = httpx.Client(
            base_url=f"https://{host}/clip/v2/resource/",
            headers={"hue-application-key": key},
            verify=verification,
            timeout=config.timeout_seconds,
            trust_env=False,
            transport=transport,
        )
        self.interval = config.request_interval_seconds
        self.clock, self.sleep = clock, sleep
        self.last_request: float | None = None

    def close(self):
        self.client.close()

    def request(self, method, path, body=None):
        if self.last_request is not None:
            self.sleep(max(0, self.interval - (self.clock() - self.last_request)))
        self.last_request = self.clock()
        try:
            response = self.client.request(method, path, json=body)
            if response.status_code in (401, 403):
                raise AuthenticationError(
                    "Hue rejected the application key; check .env HUE_USERNAME"
                )
            response.raise_for_status()
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("errors")
                or not isinstance(data.get("data"), list)
            ):
                raise BridgeError("Hue returned an invalid response or resource error")
            return data["data"]
        except (httpx.HTTPError, ValueError) as error:
            raise BridgeError(
                "Hue request failed; check bridge IP, connection and TLS configuration"
            ) from error

    def lights(self):
        return self.request("GET", "light")

    def update(self, resource_id, body):
        UUID(resource_id)
        self.request("PUT", f"light/{resource_id}", body)


class Controller:
    """Single serialized writer, coalescing desired states during an outage."""

    def __init__(self, bridge: Bridge, mapping, resources, max_retry_seconds=30):
        by_id = {r["id"]: r for r in resources}
        for channel, resource_id in mapping.items():
            if resource_id not in by_id:
                raise ValueError(f"Mapped resource for {channel} is absent from this bridge")
            if "dimming" not in by_id[resource_id]:
                raise ValueError(f"Mapped resource for {channel} does not support dimming")
        self.bridge, self.mapping, self.resources = bridge, mapping, by_id
        self.pending = {}
        self.retry_at, self.failures = 0.0, 0
        self.max_retry_seconds = max_retry_seconds

    def submit(self, targets):
        self.pending.update(targets)

    def flush(self, now):
        if now < self.retry_at:
            return False
        for channel, target in list(self.pending.items()):
            resource_id = self.mapping[channel]
            try:
                self.bridge.update(resource_id, payload(target, self.resources[resource_id]))
            except AuthenticationError:
                raise
            except BridgeError:
                self.failures += 1
                delay = min(self.max_retry_seconds, 2 ** min(self.failures - 1, 10))
                self.retry_at = now + delay
                log.warning(
                    "hue_bridge_unreachable retry_seconds=%s pending=%s", delay, len(self.pending)
                )
                return False
            del self.pending[channel]
        self.failures, self.retry_at = 0, 0.0
        return True
