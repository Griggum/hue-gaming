import threading
from pathlib import Path

from hue_core.catalog import Library, atomic_write


class ConflictError(ValueError):
    pass


class Store:
    """One server process owns the volume; revisions prevent lost browser edits."""

    def __init__(self, path: Path, seed: Path):
        self.path = path
        self.lock = threading.Lock()
        if not path.exists():
            library = Library.model_validate_json(seed.read_text(encoding="utf-8"))
            atomic_write(path, library.model_dump_json(indent=2))
        # Fail startup on damaged authoritative data, never silently reseed.
        self.read()

    def read(self) -> Library:
        return Library.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, library: Library) -> Library:
        with self.lock:
            current = self.read()
            if library.revision != current.revision:
                raise ConflictError("Profiles changed in another session. Reload before saving.")
            library = library.model_copy(update={"revision": current.revision + 1})
            atomic_write(self.path, library.model_dump_json(indent=2))
            return library
