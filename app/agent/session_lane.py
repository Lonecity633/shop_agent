from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator


class SessionLaneManager:
    """Serialize turns for one user/session while allowing other sessions to run."""

    def __init__(self) -> None:
        self._locks: dict[tuple[int, str], asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def lane(self, user_id: int, session_id: str) -> AsyncIterator[None]:
        lock = self._locks[(int(user_id), str(session_id))]
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
