"""Retry optional startup dependencies with a bounded wake-up budget."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def retry_dependency(
    name: str, initialize: Callable[[], Awaitable[object]], *, timeout: float | None = 45.0
) -> bool:
    """Retry serially up to five times; cancellation stops the loop."""
    delay = 5.0
    for attempt in range(5):
        await asyncio.sleep(delay)
        try:
            if timeout is None:
                await initialize()
            else:
                await asyncio.wait_for(initialize(), timeout=timeout)
        except Exception as exc:
            if attempt == 4:
                logger.warning("%s recovery failed; retry budget exhausted: %s", name, exc)
            else:
                logger.warning("%s recovery failed; retrying: %s", name, exc)
                delay = min(delay * 2, 60.0)
        else:
            logger.info("%s recovered", name)
            return True
    return False


class DependencyRecovery:
    """One bounded recovery task per dependency, with request-driven rearming."""

    def __init__(self, cooldown: float = 600.0) -> None:
        self._cooldown = cooldown
        self._initializers: dict[str, tuple[Callable[[], Awaitable[object]], float | None]] = {}
        self._failed: set[str] = set()
        self._tasks: dict[str, asyncio.Task] = {}
        self._last_finished: dict[str, float] = {}
        self._closed = False

    def register(
        self, name: str, initialize: Callable[[], Awaitable[object]], *,
        failed: bool, timeout: float | None = 45.0,
    ) -> None:
        self._initializers[name] = (initialize, timeout)
        if failed:
            self._failed.add(name)

    def request_recovery(self, name: str, *, failed: bool = False) -> None:
        """Schedule at most one task; only an actual request can rearm it."""
        if self._closed or name not in self._initializers:
            return
        if failed:
            self._failed.add(name)
        if name not in self._failed:
            return
        task = self._tasks.get(name)
        if task is not None and not task.done():
            return
        last = self._last_finished.get(name)
        if last is not None and time.monotonic() - last < self._cooldown:
            return
        self._tasks[name] = asyncio.create_task(self._run(name))

    async def _run(self, name: str) -> None:
        initialize, timeout = self._initializers[name]
        recovered = False
        try:
            recovered = await retry_dependency(name, initialize, timeout=timeout)
            if recovered:
                self._failed.discard(name)
        finally:
            if recovered:
                self._last_finished.pop(name, None)
            else:
                self._last_finished[name] = time.monotonic()

    async def shutdown(self) -> None:
        self._closed = True
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
