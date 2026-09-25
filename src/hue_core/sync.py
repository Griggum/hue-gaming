"""Pull-only replication, separate from the latency-sensitive gaming process."""

import argparse
import os
import ssl
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .catalog import Library, atomic_write

MAX_BYTES = 8 * 1024 * 1024


def pull(url: str, token: str, cache: Path, *, transport=None, ca_file: Path | None = None) -> bool:
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Server URL must be HTTP(S) without embedded credentials")
    if not token:
        raise ValueError("Set HUE_PORTAL_TOKEN")
    # Never use redirects or environment proxies with the portal credential.
    with (
        httpx.Client(
            timeout=5,
            trust_env=False,
            transport=transport,
            verify=ssl.create_default_context(cafile=ca_file) if ca_file else True,
        ) as client,
        client.stream(
            "GET", url.rstrip("/") + "/api/library", headers={"Authorization": f"Bearer {token}"}
        ) as response,
    ):
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError("Library exceeds cache size limit")
    library = Library.model_validate_json(bytes(data))
    content = library.model_dump_json(indent=2)
    if cache.exists() and cache.read_text(encoding="utf-8") == content:
        return False
    atomic_write(cache, content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Pull Pi profiles into a local cache")
    parser.add_argument("--server", required=True)
    parser.add_argument("--cache", type=Path, default=Path("config/profiles.cache.json"))
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--ca-file", type=Path, help="Trusted CA bundle for a private HTTPS portal")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error("Interval must be at least five seconds")
    while True:
        try:
            changed = pull(
                args.server, os.getenv("HUE_PORTAL_TOKEN", ""), args.cache, ca_file=args.ca_file
            )
            print("Cache updated" if changed else "Cache current", flush=True)
        except (httpx.HTTPError, ValueError, OSError):
            print("Sync unavailable; existing local cache retained", flush=True)
            if not args.watch:
                return 1
        if not args.watch:
            return 0
        time.sleep(args.interval)
