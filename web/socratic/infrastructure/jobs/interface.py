from collections.abc import Awaitable, Callable
from typing import Protocol


class JobRunner(Protocol):
    def run_background(self, fn: Callable[..., Awaitable], *args, **kwargs) -> None: ...
