"""Background job runner using asyncio.create_task."""

import asyncio
from collections.abc import Awaitable, Callable
import logging

logger = logging.getLogger("socratic.infrastructure.jobs")


class AsyncioJobRunner:
    def run_background(self, fn: Callable[..., Awaitable], *args, **kwargs) -> None:
        async def _wrapper():
            try:
                await fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"后台任务异常: {e}")

        _task = asyncio.create_task(_wrapper())  # noqa: RUF006
