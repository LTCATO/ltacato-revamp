"""
Generic bounded, TTL-based, in-process cache.

Single-process only: this is a plain in-memory dict, so under a multi-worker
deployment (e.g. gunicorn with multiple workers) each worker has its own copy
and entries are not shared or invalidated across workers. Fine for the
current single-process `app.run()` deployment (see main.py); if that ever
changes, this would need to move to a shared store (e.g. Redis).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, max_size: int = 500, ttl_seconds: float = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() >= expires_at:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if key in self._data:
            del self._data[key]
        self._data[key] = (value, time.time() + ttl)
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def invalidate(self, prefix: str | None = None) -> None:
        if prefix is None:
            self._data.clear()
            return
        for key in [k for k in self._data if k.startswith(prefix)]:
            del self._data[key]
