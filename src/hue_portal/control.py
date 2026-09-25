"""A single serialized Pi-side controller. No game detection or Pi-to-PC commands."""

import threading
import time

from hue_core.ambient import AmbientEngine
from hue_core.hue import BridgeError, Controller


class Player:
    def __init__(self, bridge_factory, mapping_loader):
        self.bridge_factory = bridge_factory
        self.mapping_loader = mapping_loader
        self.lock = threading.Lock()
        self.bridge = None
        self.engine = None
        self.controller = None
        self.scene_id = None
        self.error = None
        self.quit = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def play(self, scene_id, scene, lighting, ambient):
        with self.lock:
            self._stop()
            try:
                self.bridge = self.bridge_factory()
                self.controller = Controller(
                    self.bridge, self.mapping_loader(), self.bridge.lights()
                )
                engine = AmbientEngine(scene, lighting=lighting)
                self.controller.submit(engine.step(time.monotonic()))
                if not self.controller.flush(time.monotonic()):
                    raise ValueError("Scene delivery incomplete; check the bridge and retry")
                self.scene_id = scene_id
                self.error = None
                if ambient:
                    self.engine = engine
                else:
                    self.bridge.close()
                    self.bridge = None
            except Exception:
                self._stop()
                self.error = (
                    "Unable to apply scene; check bridge credentials, TLS and light mapping"
                )
                raise

    def _stop(self):
        self.engine = self.controller = None
        self.scene_id = None
        if self.bridge:
            self.bridge.close()
            self.bridge = None

    def stop(self):
        with self.lock:
            self._stop()
            self.error = None

    def status(self):
        with self.lock:
            return {"scene": self.scene_id, "ambient": self.engine is not None, "error": self.error}

    def _run(self):
        while not self.quit.wait(0.25):
            with self.lock:
                if self.engine:
                    try:
                        now = time.monotonic()
                        self.controller.submit(self.engine.step(now))
                        delivered = self.controller.flush(now)
                        self.error = None if delivered else "Bridge unavailable; retrying"
                    except (BridgeError, ValueError, OSError, KeyError):
                        self._stop()
                        self.error = "Bridge control stopped; check configuration and retry"

    def close(self):
        self.quit.set()
        self.thread.join()
        self.stop()
