from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class DiskCache:
    """Simple file-based cache keyed by arbitrary string keys."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.json"

    def get(self, key: str) -> Optional[Any]:
        p = self._path(key)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, OSError, IOError):
                return None
        return None

    def set(self, key: str, value: Any) -> None:
        self._path(key).write_text(json.dumps(value, default=str))

    def has(self, key: str) -> bool:
        return self._path(key).exists()


def hash_file(path: Path) -> str:
    """SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def hash_files(paths: list[Path]) -> str:
    """Combined SHA256 of multiple files (order-stable)."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()
