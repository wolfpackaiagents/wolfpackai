"""API-key sliding-window rate limiters."""

from __future__ import annotations

import math
import hashlib
import threading
import time
import uuid
from collections import deque


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter keyed by an authenticated API key ID."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            requests = self._requests.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.max_requests:
                retry_after = max(1, math.ceil(self.window_seconds - (now - requests[0])))
                return False, retry_after
            requests.append(now)
            return True, 0


class RedisRateLimiter:
    """Atomic, cross-replica sliding-window limiter backed by Redis sorted sets."""

    _SCRIPT = """
local key, now, window, maximum, member = KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3]), ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= maximum then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')[2]
  return {0, math.max(1, math.ceil(window - (now - tonumber(oldest))))}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window) + 1)
return {1, 0}
"""

    def __init__(self, client, max_requests: int, window_seconds: int, prefix: str):
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.prefix = prefix

    def check(self, key: str) -> tuple[bool, int]:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        allowed, retry_after = self.client.eval(
            self._SCRIPT,
            1,
            f"{self.prefix}:{key_hash}",
            time.time(),
            self.window_seconds,
            self.max_requests,
            uuid.uuid4().hex,
        )
        return bool(allowed), int(retry_after)
