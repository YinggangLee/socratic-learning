from collections.abc import AsyncIterator
from typing import Protocol


class LLMClient(Protocol):
    async def create_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> str: ...

    # Returns full text response


class AsyncLLMClient(Protocol):
    async def create_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> str: ...

    def stream_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> AsyncIterator[str]: ...

    # Yields text tokens one at a time
