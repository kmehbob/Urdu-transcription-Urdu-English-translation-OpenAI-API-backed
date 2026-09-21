import asyncio


class BoundedConcurrency:
    """Non-blocking admission guard: try_acquire() returns False immediately
    once `limit` requests are in flight, so a burst of traffic fails fast
    with 503 rather than piling up and hitting the OpenAI API's own rate
    limits."""

    def __init__(self, limit):
        self.limit = limit
        self.count = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self):
        async with self._lock:
            if self.count >= self.limit:
                return False
            self.count += 1
            return True

    async def release(self):
        async with self._lock:
            self.count = max(0, self.count - 1)
