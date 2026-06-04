"""Lightweight, opt-in file cache for Lidl Plus API responses.

Each cached value is stored as a small JSON file under a per-user OS cache
directory. Values are looked up by a logical key (endpoint + arguments) and
carry an optional expiry, so immutable data (e.g. a past receipt) can be cached
forever while volatile data (coupons, ticket lists) expires quickly.

The cache is deliberately dependency-free (standard library only) to match the
package's minimal-dependency philosophy.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Sentinel distinguishing "not cached" from a cached value that is falsy/None.
MISSING: Any = object()


def default_cache_dir() -> Path:
    """Return the per-user OS cache directory for lidl-plus.

    Follows platform conventions: ``%LOCALAPPDATA%`` on Windows,
    ``~/Library/Caches`` on macOS, and ``$XDG_CACHE_HOME`` (or ``~/.cache``)
    elsewhere. The directory is not created here; it is created lazily on first
    write so merely constructing a cache touches no filesystem.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "lidl-plus"


class FileCache:
    """JSON-file cache keyed by an arbitrary logical string."""

    def __init__(self, cache_dir: str | os.PathLike[str] | None = None) -> None:
        self._dir = Path(cache_dir) if cache_dir else default_cache_dir()

    @property
    def directory(self) -> Path:
        """The directory cache files are stored in."""
        return self._dir

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, key: str) -> Any:
        """Return the cached value for ``key``, or ``MISSING`` if absent/expired."""
        try:
            with self._path(key).open("r", encoding="utf-8") as handle:
                entry = json.load(handle)
        except (OSError, ValueError):
            return MISSING
        expires = entry.get("expires")
        if expires is not None and time.time() >= expires:
            self.delete(key)
            return MISSING
        return entry.get("data", MISSING)

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Cache ``value`` under ``key``.

        ``ttl`` is the time-to-live in seconds; ``None`` means the entry never
        expires. The write is atomic so an interrupted write cannot leave a
        corrupt cache file behind.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        entry = {"expires": None if ttl is None else time.time() + ttl, "data": value}
        descriptor, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(entry, handle)
            os.replace(tmp, self._path(key))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def delete(self, key: str) -> None:
        """Remove a single cache entry; no error if it does not exist."""
        try:
            self._path(key).unlink()
        except OSError:
            pass

    def clear(self) -> None:
        """Remove every cache entry in the cache directory."""
        if not self._dir.is_dir():
            return
        for path in self._dir.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass


def cached(cache: FileCache | None, key: str, ttl: float | None, producer: Callable[[], Any]) -> Any:
    """Return ``key`` from ``cache`` if fresh, otherwise call ``producer`` and store it.

    When ``cache`` is ``None`` (caching disabled) ``producer`` is always called
    and nothing is stored, so callers can stay cache-agnostic.
    """
    if cache is None:
        return producer()
    value = cache.get(key)
    if value is not MISSING:
        return value
    value = producer()
    cache.set(key, value, ttl)
    return value
