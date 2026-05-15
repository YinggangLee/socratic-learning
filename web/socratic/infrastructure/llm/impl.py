"""Anthropic-compatible LLM client implementation."""

from collections.abc import AsyncIterator
import logging

from anthropic import AsyncAnthropic

from .errors import LLMCallError, LLMStreamError

logger = logging.getLogger("socratic.infrastructure.llm")


class AnthropicLLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = "", max_tokens: int = 4096):
        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncAnthropic(base_url=base_url, api_key=api_key)

    async def create_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> str:
        try:
            response = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                thinking={"type": "disabled"},
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            if text_blocks:
                return text_blocks[0].text
            return ""
        except Exception as e:
            raise LLMCallError(str(e)) from e

    async def stream_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> AsyncIterator[str]:
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                thinking={"type": "disabled"},
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
        except Exception as e:
            raise LLMStreamError(str(e)) from e
