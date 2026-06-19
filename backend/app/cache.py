"""Redis cache with graceful in-process fallback.

If Redis is unreachable the app keeps working using a bounded in-memory dict,
so local dev needs no Redis. JSON-serializable values only.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from .config import get_settings

settings = get_settings()
_redis = None
_local: "OrderedDict[str, str]" = OrderedDict()
_LOCAL_MAX = 512


def _client():
    global _redis
    if _redis is None:
        try:
            import redis
            _redis = redis.Redis.from_url(settings.redis_url,
                                          decode_responses=True)
            _redis.ping()
        except Exception:
            _redis = False  # mark unavailable
    return _redis or None


def get(key: str):
    c = _client()
    if c:
        v = c.get(key)
        return json.loads(v) if v else None
    v = _local.get(key)
    return json.loads(v) if v else None


def set(key: str, value, ttl: int | None = None):
    payload = json.dumps(value)
    c = _client()
    if c:
        c.setex(key, ttl or settings.cache_ttl, payload)
        return
    _local[key] = payload
    _local.move_to_end(key)
    while len(_local) > _LOCAL_MAX:
        _local.popitem(last=False)


def clear(prefix: str = ""):
    c = _client()
    if c:
        for k in c.scan_iter(f"{prefix}*"):
            c.delete(k)
        return
    for k in [k for k in _local if k.startswith(prefix)]:
        _local.pop(k, None)
