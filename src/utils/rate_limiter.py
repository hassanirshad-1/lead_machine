"""Generic async rate limiter for API calls."""

import asyncio
import time


class RateLimiter:
    """Token-bucket rate limiter for controlling API request frequency.

    Usage:
        limiter = RateLimiter(max_per_second=10)
        async with limiter:
            await make_api_call()
    """

    def __init__(self, max_per_second: int = 10):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def __aenter__(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()
        return self

    async def __aexit__(self, *exc):
        pass

    async def wait(self):
        """Explicit wait method (alternative to context manager)."""
        async with self:
            pass
