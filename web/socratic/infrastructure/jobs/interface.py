from typing import Protocol, Callable, Awaitable


class JobRunner(Protocol):
    def run_background(self, fn: Callable[..., Awaitable], *args, **kwargs) -> None: ...
